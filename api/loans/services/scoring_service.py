"""
Servicio de scoring crediticio con IA (CU-15, SP3-89, SP3-90).

Orquesta:
1. Consulta a buró de crédito
2. Extracción de features
3. Cálculo de sub-scores heurísticos
4. Predicción de score IA (ML o fallback heurístico)
5. Score ponderado final (60% IA + 40% Buró)
6. Evaluación de elegibilidad
7. Decisión automática basada en thresholds
"""

import logging
import time
from decimal import Decimal
from typing import Dict, Optional, Tuple
from django.utils import timezone

from api.loans.models import LoanApplication
from api.loans.models_scoring import CreditEvaluation, CreditBureauQuery, ModelRegistry
from api.loans.services.credit_bureau_service import CreditBureauService, CreditBureauError

logger = logging.getLogger(__name__)


class ScoringService:
    """
    Servicio principal de scoring crediticio.

    Este servicio es llamado por WorkflowService._execute_pre_transition_actions()
    cuando la solicitud transiciona a estado SCORING.
    """

    IA_WEIGHT = 0.6
    BUREAU_WEIGHT = 0.4

    # Cache para resultado de Groq durante la misma ejecución
    _groq_result: Optional[Dict] = None

    @classmethod
    def calculate_score(cls, application: LoanApplication) -> CreditEvaluation:
        """
        Calcula el score crediticio completo para una solicitud.

        Args:
            application: LoanApplication instance

        Returns:
            CreditEvaluation: Evaluación completa
        """
        start_time = time.time()

        # Obtener o crear evaluación
        evaluation, created = CreditEvaluation.objects.get_or_create(
            institution=application.institution,
            application=application,
            defaults={'status': CreditEvaluation.EvaluationStatus.IN_PROGRESS}
        )

        if not created:
            evaluation.status = CreditEvaluation.EvaluationStatus.IN_PROGRESS
            evaluation.save(update_fields=['status'])

        try:
            # Paso 1: Consultar buró de crédito
            bureau_query = cls._query_bureau(application)

            # Paso 2: Extraer features
            features = cls._extract_features(application, bureau_query)

            # Paso 3: Calcular score IA (Groq → ML → heurístico)
            cls._groq_result = None
            score_ia = cls._predict_score(features)
            groq_result = cls._groq_result  # Puede ser None si falló

            # Paso 4: Score ponderado final
            score_bureau = bureau_query.score_external or 500
            score_weighted = cls._calculate_weighted_score(score_ia, score_bureau)

            # Paso 5: Sub-scores (Groq o heurístico)
            if groq_result and groq_result.get('sub_scores'):
                groq_sub = groq_result['sub_scores']
                sub_scores = {
                    'payment_capacity': int(groq_sub.get('payment_capacity', 50)),
                    'employment_stability': int(groq_sub.get('employment_stability', 50)),
                    'credit_history': int(groq_sub.get('credit_history', 50)),
                    'debt_burden': int(groq_sub.get('debt_burden', 50)),
                    'demographic': int(groq_sub.get('demographic', 50)),
                }
            else:
                sub_scores = cls._calculate_sub_scores(features)

            # Paso 6: Evaluar elegibilidad
            eligibility_passed = cls._check_eligibility(application, features, score_weighted)

            # Paso 7: Determinar decisión automática (Groq o heurístico)
            if groq_result and groq_result.get('auto_decision'):
                auto_decision = groq_result['auto_decision']
                auto_reason = groq_result.get('auto_decision_reason', '')
            else:
                auto_decision, auto_reason = cls._determine_auto_decision(
                    application, score_weighted, features
                )

            # Actualizar evaluación
            evaluation.status = CreditEvaluation.EvaluationStatus.COMPLETED
            evaluation.score_ia = score_ia
            evaluation.score_bureau = score_bureau
            evaluation.score_weighted = score_weighted
            evaluation.payment_capacity_score = sub_scores['payment_capacity']
            evaluation.employment_stability_score = sub_scores['employment_stability']
            evaluation.credit_history_score = sub_scores['credit_history']
            evaluation.debt_burden_score = sub_scores['debt_burden']
            evaluation.demographic_score = sub_scores['demographic']
            evaluation.dti_calculated = features['dti_ratio']
            evaluation.recommended_amount = cls._calculate_recommended_amount(application, features)
            evaluation.max_affordable_payment = features['max_affordable_payment']
            evaluation.features_used = {
                k: float(v) if isinstance(v, Decimal) else v
                for k, v in features.items()
            }
            evaluation.model_version = (
                groq_result.get('model_version')
                if groq_result and groq_result.get('model_version')
                else cls._get_active_model_version()
            )
            evaluation.model_metadata = (
                {
                    'ia_engine': 'groq-llama-3.3-70b-versatile',
                    'analysis_summary': groq_result.get('analysis_summary', ''),
                    'risk_factors': groq_result.get('risk_factors', []),
                    'mitigants': groq_result.get('mitigants', []),
                }
                if groq_result else {}
            )
            evaluation.eligibility_check_passed = eligibility_passed
            evaluation.bureau_check_passed = True
            evaluation.auto_decision = auto_decision
            evaluation.auto_decision_reason = auto_reason
            evaluation.evaluated_at = timezone.now()
            evaluation.evaluation_time_ms = int((time.time() - start_time) * 1000)
            evaluation.save()

            # Limpiar cache
            cls._groq_result = None

            # Actualizar LoanApplication con el score
            application.credit_score = score_weighted
            application.risk_level = cls._score_to_risk_level(score_weighted)
            application.debt_to_income_ratio = features['dti_ratio']
            application.save(update_fields=['credit_score', 'risk_level', 'debt_to_income_ratio'])

            logger.info(
                f"[SCORING] Evaluación completada: {application.application_number} "
                f"Score={score_weighted}, Decisión={auto_decision}, "
                f"Tiempo={evaluation.evaluation_time_ms}ms"
            )

        except Exception as e:
            evaluation.status = CreditEvaluation.EvaluationStatus.FAILED
            evaluation.error_message = str(e)
            evaluation.save(update_fields=['status', 'error_message'])
            logger.error(
                f"[SCORING] Error en evaluación {application.id}: {str(e)}",
                exc_info=True
            )
            raise

        return evaluation

    @classmethod
    def _query_bureau(cls, application: LoanApplication) -> CreditBureauQuery:
        """
        Consulta buró de crédito con fallback.

        Args:
            application: LoanApplication instance

        Returns:
            CreditBureauQuery: Consulta exitosa o fallida
        """
        try:
            return CreditBureauService.query_bureau(application)
        except CreditBureauError as e:
            logger.warning(f"[SCORING] Buró falló, usando defaults: {str(e)}")
            return CreditBureauQuery.objects.create(
                institution=application.institution,
                application=application,
                provider='SIMULATED',
                status=CreditBureauQuery.QueryStatus.FAILED,
                error_message=str(e)
            )

    @classmethod
    def _extract_features(
        cls, application: LoanApplication, bureau_query: CreditBureauQuery
    ) -> Dict:
        """
        Extrae features del modelo a partir de la solicitud y buró.

        Args:
            application: LoanApplication instance
            bureau_query: CreditBureauQuery instance

        Returns:
            Dict: Features extraídas para el modelo
        """
        monthly_income = float(application.monthly_income or 0)
        requested_amount = float(application.requested_amount)
        debt_total = float(bureau_query.debt_total or 0)

        # Calcular DTI
        total_monthly_debt = debt_total / 12
        dti_ratio = Decimal(str(round(
            ((total_monthly_debt + (requested_amount / application.term_months))
             / max(monthly_income, 1)) * 100,
            2
        )))

        # Cuota máxima asequible (40% del ingreso)
        max_affordable_payment = monthly_income * 0.40

        features = {
            'monthly_income': monthly_income,
            'requested_amount': requested_amount,
            'term_months': application.term_months,
            'employment_type': application.employment_type or '',
            'dti_ratio': dti_ratio,
            'debt_total': debt_total,
            'bureau_score': float(bureau_query.score_external or 500),
            'has_defaults': bool(bureau_query.has_defaults),
            'cic_category': bureau_query.cic_category or 'N/A',
            'max_affordable_payment': max_affordable_payment,
            'amount_to_income_ratio': requested_amount / max(monthly_income, 1),
            'payment_to_income': (
                (requested_amount / max(application.term_months, 1))
                / max(monthly_income, 1)
            ),
        }

        return features

    @classmethod
    def _calculate_sub_scores(cls, features: Dict) -> Dict[str, int]:
        """
        Calcula sub-scores heurísticos (0-100 cada uno).

        Args:
            features: Diccionario de features extraídas

        Returns:
            Dict: Sub-scores por factor
        """
        # Capacidad de pago: basada en DTI
        dti = float(features['dti_ratio'])
        if dti <= 20:
            payment_capacity = 90
        elif dti <= 30:
            payment_capacity = 75
        elif dti <= 40:
            payment_capacity = 55
        elif dti <= 50:
            payment_capacity = 35
        else:
            payment_capacity = 15

        # Estabilidad laboral
        emp_type = features.get('employment_type', '')
        if emp_type in ('EMPLOYED', 'BUSINESS_OWNER'):
            employment_stability = 70
        elif emp_type == 'SELF_EMPLOYED':
            employment_stability = 55
        elif emp_type == 'RETIRED':
            employment_stability = 80
        else:
            employment_stability = 30

        # Historial crediticio (basado en buró)
        bureau = features.get('bureau_score', 500)
        if bureau >= 700:
            credit_history = 85
        elif bureau >= 600:
            credit_history = 65
        elif bureau >= 450:
            credit_history = 40
        else:
            credit_history = 20
        if features.get('has_defaults'):
            credit_history = max(10, credit_history - 30)

        # Carga de deuda
        debt_ratio = float(features.get('amount_to_income_ratio', 5))
        if debt_ratio <= 1:
            debt_burden = 85
        elif debt_ratio <= 3:
            debt_burden = 65
        elif debt_ratio <= 6:
            debt_burden = 40
        else:
            debt_burden = 20

        # Perfil demográfico
        demographic = 65

        return {
            'payment_capacity': payment_capacity,
            'employment_stability': employment_stability,
            'credit_history': credit_history,
            'debt_burden': debt_burden,
            'demographic': demographic,
        }

    @classmethod
    def _predict_score(cls, features: Dict) -> int:
        """
        Predice score usando Groq LLM, modelo ML o fallback heurístico.

        Orden de prioridad:
        1. Groq LLM (llama-3.3-70b-versatile)
        2. Modelo ML scikit-learn (si existe y está activo)
        3. Heurístico basado en reglas

        Args:
            features: Diccionario de features

        Returns:
            int: Score IA (0-1000)
        """
        # 1. Intentar con Groq LLM
        try:
            groq_result = cls._evaluate_with_groq(features)
            if groq_result:
                cls._groq_result = groq_result  # Cache para uso en calculate_score
                return int(groq_result['score_ia'])
        except Exception as e:
            logger.warning(
                f"[SCORING] Groq no disponible, intentando ML: {str(e)}"
            )

        # 2. Intentar con modelo ML scikit-learn
        try:
            model_registry = ModelRegistry.objects.filter(is_active=True).first()
            if model_registry and model_registry.status == ModelRegistry.ModelStatus.ACTIVE:
                return cls._predict_with_ml_model(features, model_registry)
        except Exception as e:
            logger.warning(
                f"[SCORING] Modelo ML no disponible, usando heurístico: {str(e)}"
            )

        # 3. Fallback: score heurístico ponderado
        sub_scores = cls._calculate_sub_scores(features)
        heuristic_score = int(
            sub_scores['payment_capacity'] * 2.5 +
            sub_scores['employment_stability'] * 1.5 +
            sub_scores['credit_history'] * 3.0 +
            sub_scores['debt_burden'] * 2.0 +
            sub_scores['demographic'] * 1.0
        )
        return min(1000, max(0, heuristic_score))

    @classmethod
    def _evaluate_with_groq(cls, features: Dict) -> Optional[Dict]:
        """
        Evalúa crédito con Groq LLM.

        Args:
            features: Diccionario de features

        Returns:
            Dict con score_ia, sub_scores, auto_decision, etc. o None si falla
        """
        from api.loans.services.groq_scorer import groq_scorer, GroqScoringError

        try:
            result = groq_scorer.evaluate_credit(features)
            logger.info(
                f"[SCORING] Groq evaluó: score_ia={result.get('score_ia')}, "
                f"decisión={result.get('auto_decision')}"
            )
            return result
        except GroqScoringError as e:
            logger.warning(f"[SCORING] Groq falló: {str(e)}")
            return None
        except Exception as e:
            logger.warning(f"[SCORING] Error inesperado en Groq: {str(e)}")
            return None

    @classmethod
    def _predict_with_ml_model(
        cls, features: Dict, model_registry: ModelRegistry
    ) -> int:
        """
        Predice usando modelo ML cargado desde disco.

        Args:
            features: Diccionario de features
            model_registry: ModelRegistry con ruta del modelo

        Returns:
            int: Score predicho (0-1000)
        """
        import os
        import joblib

        model_path = model_registry.model_path
        if not model_path or not os.path.exists(model_path):
            raise FileNotFoundError(f"Modelo no encontrado: {model_path}")

        model = joblib.load(model_path)

        feature_values = []
        for fname in model_registry.feature_names:
            val = features.get(fname, 0)
            feature_values.append(float(val) if not isinstance(val, (int, float)) else val)

        import numpy as np
        X = np.array(feature_values).reshape(1, -1)
        prediction = model.predict(X)[0]

        return int(max(0, min(1000, prediction)))

    @classmethod
    def _get_active_model_version(cls) -> str:
        """
        Obtiene la versión del modelo activo.

        Returns:
            str: Versión del modelo o 'HEURISTIC-v1'
        """
        try:
            model = ModelRegistry.objects.filter(is_active=True).first()
            return model.version if model else 'HEURISTIC-v1'
        except Exception:
            return 'HEURISTIC-v1'

    @classmethod
    def _calculate_weighted_score(cls, score_ia: int, score_bureau: int) -> int:
        """
        Calcula score ponderado final (60% IA + 40% Buró).

        Args:
            score_ia: Score del modelo IA
            score_bureau: Score del buró

        Returns:
            int: Score ponderado (0-1000)
        """
        return int((score_ia * cls.IA_WEIGHT) + (score_bureau * cls.BUREAU_WEIGHT))

    @classmethod
    def _check_eligibility(
        cls, application: LoanApplication, features: Dict, score: int
    ) -> bool:
        """
        Evalúa reglas de elegibilidad del RuleSet.

        Args:
            application: LoanApplication
            features: Features extraídas
            score: Score ponderado

        Returns:
            bool: True si pasa todas las reglas
        """
        try:
            if not application.rule_set_snapshot:
                return True

            eligibility = getattr(
                application.rule_set_snapshot, 'eligibility_rule', None
            )
            if not eligibility:
                return True

            threshold = getattr(
                application.rule_set_snapshot, 'decision_threshold', None
            )
            if threshold and score < threshold.max_score_auto_rejection:
                return False

            dti = float(features.get('dti_ratio', 0))
            max_dti = float(eligibility.max_debt_to_income_ratio)
            if dti > max_dti:
                return False

            return True

        except Exception as e:
            logger.error(f"[SCORING] Error en elegibilidad: {str(e)}")
            return True

    @classmethod
    def _determine_auto_decision(
        cls, application: LoanApplication, score: int, features: Dict
    ) -> Tuple[str, str]:
        """
        Determina decisión automática basada en thresholds.

        Args:
            application: LoanApplication
            score: Score ponderado
            features: Features extraídas

        Returns:
            Tuple[str, str]: (decisión, razón)
        """
        threshold = None
        if application.rule_set_snapshot:
            threshold = getattr(
                application.rule_set_snapshot, 'decision_threshold', None
            )

        if not threshold:
            return (
                'MANUAL_REVIEW',
                'Sin umbrales configurados. Requiere revisión manual.'
            )

        if score >= threshold.min_score_auto_approval:
            return (
                'APPROVE',
                f'Score {score} ≥ {threshold.min_score_auto_approval}. '
                f'Aprobación automática.'
            )

        if score <= threshold.max_score_auto_rejection:
            dti = float(features.get('dti_ratio', 0))
            reason = (
                f'Score {score} ≤ {threshold.max_score_auto_rejection}.'
            )
            try:
                eligibility = getattr(
                    application.rule_set_snapshot, 'eligibility_rule', None
                )
                if eligibility and dti > float(eligibility.max_debt_to_income_ratio):
                    reason += f' DTI elevado ({dti:.1f}%).'
            except Exception:
                pass
            return ('REJECT', reason)

        # Evaluar si requiere escalamiento
        monto_max = getattr(threshold, 'requires_manager_approval_amount', None)
        if monto_max and float(application.requested_amount) > float(monto_max):
            return (
                'ESCALATE',
                f'Monto {application.requested_amount} excede límite '
                f'de aprobación automática.'
            )

        return (
            'MANUAL_REVIEW',
            f'Score {score} en zona de revisión manual.'
        )

    @classmethod
    def _calculate_recommended_amount(
        cls, application: LoanApplication, features: Dict
    ) -> Decimal:
        """
        Calcula monto recomendado basado en capacidad de pago.

        Args:
            application: LoanApplication
            features: Features extraídas

        Returns:
            Decimal: Monto recomendado
        """
        max_payment = Decimal(str(features.get('max_affordable_payment', 0)))
        term = application.term_months
        recommended = max_payment * term * Decimal('0.8')
        return Decimal(str(round(
            min(float(recommended), float(application.requested_amount)), 2
        )))

    @classmethod
    def _score_to_risk_level(cls, score: int) -> str:
        """
        Convierte score a nivel de riesgo.

        Args:
            score: Score (0-1000)

        Returns:
            str: Nivel de riesgo (LOW/MEDIUM/HIGH/VERY_HIGH)
        """
        if score >= 800:
            return 'LOW'
        elif score >= 600:
            return 'MEDIUM'
        elif score >= 400:
            return 'HIGH'
        else:
            return 'VERY_HIGH'
