"""
Servicio de generación de gráficos para reportes.

Genera gráficos profesionales usando Matplotlib:
- Gráficos de barras
- Gráficos de líneas
- Gráficos circulares/dona
- Gráficos de barras apiladas
"""
import io
import logging
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal

try:
    import matplotlib
    matplotlib.use('Agg')  # Backend sin GUI para servidor
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.figure import Figure
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


class ChartGeneratorService:
    """
    Servicio de generación de gráficos para reportes.
    
    Genera gráficos profesionales con Matplotlib y los exporta
    como imágenes PNG para incrustar en PDFs.
    """
    
    # Colores corporativos
    COLOR_PRIMARY = '#1F4E78'  # Azul corporativo
    COLOR_SECONDARY = '#4472C4'  # Azul claro
    COLOR_ACCENT = '#ED7D31'  # Naranja
    COLOR_SUCCESS = '#70AD47'  # Verde
    COLOR_WARNING = '#FFC000'  # Amarillo
    COLOR_DANGER = '#C00000'  # Rojo
    
    # Paleta de colores para múltiples series
    COLOR_PALETTE = [
        '#4472C4',  # Azul
        '#ED7D31',  # Naranja
        '#70AD47',  # Verde
        '#FFC000',  # Amarillo
        '#5B9BD5',  # Azul claro
        '#C55A11',  # Naranja oscuro
        '#548235',  # Verde oscuro
        '#997300',  # Amarillo oscuro
    ]
    
    # Tipos de gráficos soportados
    CHART_TYPES = {
        'BAR': 'bar',
        'HORIZONTAL_BAR': 'barh',
        'LINE': 'line',
        'PIE': 'pie',
        'DONUT': 'donut',
        'STACKED_BAR': 'stacked_bar',
    }
    
    def __init__(self):
        """Inicializa el servicio de generación de gráficos."""
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError(
                "matplotlib no está instalado. "
                "Instalar con: pip install matplotlib"
            )
        
        # Configurar estilo global
        plt.style.use('seaborn-v0_8-darkgrid')
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
        plt.rcParams['font.size'] = 10
        plt.rcParams['axes.labelsize'] = 11
        plt.rcParams['axes.titlesize'] = 13
        plt.rcParams['xtick.labelsize'] = 9
        plt.rcParams['ytick.labelsize'] = 9
        plt.rcParams['legend.fontsize'] = 9
        plt.rcParams['figure.titlesize'] = 14
    
    def generate_chart(
        self,
        chart_type: str,
        data: List[Dict[str, Any]],
        config: Dict[str, Any]
    ) -> bytes:
        """
        Genera un gráfico según el tipo especificado.
        
        Args:
            chart_type: Tipo de gráfico (BAR, LINE, PIE, etc.)
            data: Datos del reporte
            config: Configuración del gráfico (título, ejes, series, etc.)
        
        Returns:
            Imagen PNG del gráfico en bytes
        
        Raises:
            ValueError: Si el tipo de gráfico no es soportado
        """
        if not data:
            raise ValueError("No hay datos para generar el gráfico")
        
        chart_type_upper = chart_type.upper()
        if chart_type_upper not in self.CHART_TYPES:
            raise ValueError(
                f"Tipo de gráfico no soportado: {chart_type}. "
                f"Tipos disponibles: {list(self.CHART_TYPES.keys())}"
            )
        
        logger.info(f"Generando gráfico tipo {chart_type_upper}")
        
        # Crear figura
        fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
        
        # Generar gráfico según tipo
        if chart_type_upper == 'BAR':
            self._generate_bar_chart(ax, data, config)
        elif chart_type_upper == 'HORIZONTAL_BAR':
            self._generate_horizontal_bar_chart(ax, data, config)
        elif chart_type_upper == 'LINE':
            self._generate_line_chart(ax, data, config)
        elif chart_type_upper == 'PIE':
            self._generate_pie_chart(ax, data, config)
        elif chart_type_upper == 'DONUT':
            self._generate_donut_chart(ax, data, config)
        elif chart_type_upper == 'STACKED_BAR':
            self._generate_stacked_bar_chart(ax, data, config)
        
        # Ajustar layout
        plt.tight_layout()
        
        # Exportar a bytes
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        
        buffer.seek(0)
        image_bytes = buffer.read()
        buffer.close()
        
        logger.info(f"Gráfico generado exitosamente. Tamaño: {len(image_bytes)} bytes")
        return image_bytes
    
    def _generate_bar_chart(
        self,
        ax,
        data: List[Dict[str, Any]],
        config: Dict[str, Any]
    ):
        """Genera gráfico de barras verticales."""
        x_field = config.get('x_field', 'category')
        y_field = config.get('y_field', 'value')
        title = config.get('title', 'Gráfico de Barras')
        x_label = config.get('x_axis', 'Categoría')
        y_label = config.get('y_axis', 'Valor')
        
        # Extraer datos
        categories = []
        values = []
        for row in data[:15]:  # Limitar a 15 categorías
            cat = str(row.get(x_field, ''))
            val = self._to_number(row.get(y_field, 0))
            if cat and val is not None:
                categories.append(cat)
                values.append(val)
        
        if not categories:
            raise ValueError("No hay datos válidos para el gráfico")
        
        # Crear gráfico
        bars = ax.bar(
            range(len(categories)),
            values,
            color=self.COLOR_SECONDARY,
            edgecolor='white',
            linewidth=1.2
        )
        
        # Agregar valores sobre las barras
        for i, (bar, value) in enumerate(zip(bars, values)):
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height,
                self._format_number(value),
                ha='center',
                va='bottom',
                fontsize=9,
                fontweight='bold'
            )
        
        # Configurar ejes
        ax.set_xticks(range(len(categories)))
        ax.set_xticklabels(categories, rotation=45, ha='right')
        ax.set_xlabel(x_label, fontweight='bold')
        ax.set_ylabel(y_label, fontweight='bold')
        ax.set_title(title, fontweight='bold', pad=20)
        ax.grid(axis='y', alpha=0.3)
        ax.set_axisbelow(True)
    
    def _generate_horizontal_bar_chart(
        self,
        ax,
        data: List[Dict[str, Any]],
        config: Dict[str, Any]
    ):
        """Genera gráfico de barras horizontales."""
        x_field = config.get('x_field', 'category')
        y_field = config.get('y_field', 'value')
        title = config.get('title', 'Gráfico de Barras Horizontales')
        x_label = config.get('x_axis', 'Valor')
        y_label = config.get('y_axis', 'Categoría')
        
        # Extraer datos
        categories = []
        values = []
        for row in data[:15]:
            cat = str(row.get(x_field, ''))
            val = self._to_number(row.get(y_field, 0))
            if cat and val is not None:
                categories.append(cat)
                values.append(val)
        
        if not categories:
            raise ValueError("No hay datos válidos para el gráfico")
        
        # Ordenar por valor (opcional)
        if config.get('sort_by_value', True):
            sorted_data = sorted(zip(categories, values), key=lambda x: x[1], reverse=True)
            categories, values = zip(*sorted_data)
            categories = list(categories)
            values = list(values)
        
        # Crear gráfico
        bars = ax.barh(
            range(len(categories)),
            values,
            color=self.COLOR_SECONDARY,
            edgecolor='white',
            linewidth=1.2
        )
        
        # Agregar valores al final de las barras
        for i, (bar, value) in enumerate(zip(bars, values)):
            width = bar.get_width()
            ax.text(
                width,
                bar.get_y() + bar.get_height() / 2,
                f' {self._format_number(value)}',
                ha='left',
                va='center',
                fontsize=9,
                fontweight='bold'
            )
        
        # Configurar ejes
        ax.set_yticks(range(len(categories)))
        ax.set_yticklabels(categories)
        ax.set_xlabel(x_label, fontweight='bold')
        ax.set_ylabel(y_label, fontweight='bold')
        ax.set_title(title, fontweight='bold', pad=20)
        ax.grid(axis='x', alpha=0.3)
        ax.set_axisbelow(True)
    
    def _generate_line_chart(
        self,
        ax,
        data: List[Dict[str, Any]],
        config: Dict[str, Any]
    ):
        """Genera gráfico de líneas."""
        x_field = config.get('x_field', 'date')
        y_field = config.get('y_field', 'value')
        title = config.get('title', 'Gráfico de Líneas')
        x_label = config.get('x_axis', 'Período')
        y_label = config.get('y_axis', 'Valor')
        
        # Extraer datos
        x_values = []
        y_values = []
        for row in data:
            x_val = row.get(x_field)
            y_val = self._to_number(row.get(y_field, 0))
            if x_val is not None and y_val is not None:
                x_values.append(str(x_val))
                y_values.append(y_val)
        
        if not x_values:
            raise ValueError("No hay datos válidos para el gráfico")
        
        # Crear gráfico
        ax.plot(
            range(len(x_values)),
            y_values,
            color=self.COLOR_PRIMARY,
            linewidth=2.5,
            marker='o',
            markersize=6,
            markerfacecolor=self.COLOR_SECONDARY,
            markeredgecolor='white',
            markeredgewidth=1.5
        )
        
        # Agregar valores en los puntos
        for i, (x, y) in enumerate(zip(range(len(x_values)), y_values)):
            ax.text(
                x,
                y,
                self._format_number(y),
                ha='center',
                va='bottom',
                fontsize=8,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7, edgecolor='none')
            )
        
        # Configurar ejes
        ax.set_xticks(range(len(x_values)))
        ax.set_xticklabels(x_values, rotation=45, ha='right')
        ax.set_xlabel(x_label, fontweight='bold')
        ax.set_ylabel(y_label, fontweight='bold')
        ax.set_title(title, fontweight='bold', pad=20)
        ax.grid(True, alpha=0.3)
        ax.set_axisbelow(True)
    
    def _generate_pie_chart(
        self,
        ax,
        data: List[Dict[str, Any]],
        config: Dict[str, Any]
    ):
        """Genera gráfico circular."""
        label_field = config.get('label_field', 'category')
        value_field = config.get('value_field', 'value')
        title = config.get('title', 'Gráfico Circular')
        
        # Extraer datos
        labels = []
        values = []
        for row in data[:10]:  # Limitar a 10 categorías
            label = str(row.get(label_field, ''))
            value = self._to_number(row.get(value_field, 0))
            if label and value and value > 0:
                labels.append(label)
                values.append(value)
        
        if not labels:
            raise ValueError("No hay datos válidos para el gráfico")
        
        # Calcular porcentajes
        total = sum(values)
        percentages = [(v / total) * 100 for v in values]
        
        # Crear gráfico
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            autopct='%1.1f%%',
            startangle=90,
            colors=self.COLOR_PALETTE[:len(labels)],
            wedgeprops=dict(edgecolor='white', linewidth=2),
            textprops=dict(color='black', fontweight='bold')
        )
        
        # Mejorar legibilidad de porcentajes
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(10)
            autotext.set_fontweight('bold')
        
        ax.set_title(title, fontweight='bold', pad=20)
        ax.axis('equal')
    
    def _generate_donut_chart(
        self,
        ax,
        data: List[Dict[str, Any]],
        config: Dict[str, Any]
    ):
        """Genera gráfico de dona."""
        label_field = config.get('label_field', 'category')
        value_field = config.get('value_field', 'value')
        title = config.get('title', 'Gráfico de Dona')
        
        # Extraer datos
        labels = []
        values = []
        for row in data[:10]:
            label = str(row.get(label_field, ''))
            value = self._to_number(row.get(value_field, 0))
            if label and value and value > 0:
                labels.append(label)
                values.append(value)
        
        if not labels:
            raise ValueError("No hay datos válidos para el gráfico")
        
        # Crear gráfico
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            autopct='%1.1f%%',
            startangle=90,
            colors=self.COLOR_PALETTE[:len(labels)],
            wedgeprops=dict(width=0.4, edgecolor='white', linewidth=2),
            textprops=dict(color='black', fontweight='bold')
        )
        
        # Mejorar legibilidad
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(10)
            autotext.set_fontweight('bold')
        
        # Agregar círculo central
        centre_circle = plt.Circle((0, 0), 0.60, fc='white')
        ax.add_artist(centre_circle)
        
        ax.set_title(title, fontweight='bold', pad=20)
        ax.axis('equal')
    
    def _generate_stacked_bar_chart(
        self,
        ax,
        data: List[Dict[str, Any]],
        config: Dict[str, Any]
    ):
        """Genera gráfico de barras apiladas."""
        x_field = config.get('x_field', 'category')
        series_fields = config.get('series_fields', ['value1', 'value2'])
        series_labels = config.get('series_labels', series_fields)
        title = config.get('title', 'Gráfico de Barras Apiladas')
        x_label = config.get('x_axis', 'Categoría')
        y_label = config.get('y_axis', 'Valor')
        
        # Extraer datos
        categories = []
        series_data = {field: [] for field in series_fields}
        
        for row in data[:15]:
            cat = str(row.get(x_field, ''))
            if cat:
                categories.append(cat)
                for field in series_fields:
                    value = self._to_number(row.get(field, 0))
                    series_data[field].append(value if value is not None else 0)
        
        if not categories:
            raise ValueError("No hay datos válidos para el gráfico")
        
        # Crear gráfico apilado
        x_pos = np.arange(len(categories))
        bottom = np.zeros(len(categories))
        
        for i, (field, label) in enumerate(zip(series_fields, series_labels)):
            values = series_data[field]
            ax.bar(
                x_pos,
                values,
                bottom=bottom,
                label=label,
                color=self.COLOR_PALETTE[i % len(self.COLOR_PALETTE)],
                edgecolor='white',
                linewidth=1
            )
            bottom += np.array(values)
        
        # Configurar ejes
        ax.set_xticks(x_pos)
        ax.set_xticklabels(categories, rotation=45, ha='right')
        ax.set_xlabel(x_label, fontweight='bold')
        ax.set_ylabel(y_label, fontweight='bold')
        ax.set_title(title, fontweight='bold', pad=20)
        ax.legend(loc='upper right', framealpha=0.9)
        ax.grid(axis='y', alpha=0.3)
        ax.set_axisbelow(True)
    
    def _to_number(self, value: Any) -> Optional[float]:
        """Convierte un valor a número."""
        if value is None:
            return None
        
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, Decimal):
            return float(value)
        
        if isinstance(value, str):
            try:
                # Intentar convertir string a número
                cleaned = value.replace(',', '').replace('$', '').strip()
                return float(cleaned)
            except (ValueError, AttributeError):
                return None
        
        return None
    
    def _format_number(self, value: float) -> str:
        """Formatea un número para mostrar."""
        if value >= 1_000_000:
            return f'{value/1_000_000:.1f}M'
        elif value >= 1_000:
            return f'{value/1_000:.1f}K'
        elif value % 1 == 0:
            return f'{int(value):,}'
        else:
            return f'{value:,.1f}'
