import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from shapely.geometry import Point

# Configuración de la página
st.set_page_config(
    page_title="Análisis FNA - Oficinas Colombia",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem 0;
        margin-bottom: 2rem;
        border-radius: 10px;
    }
    .metric-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
    }
    .section-card {
        background-color: white;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 2rem;
    }
    .section-header {
        background-color: #2c3e50;
        color: white;
        padding: 1rem;
        margin: 0;
        border-radius: 10px 10px 0 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_and_process_data():
    """Cargar y procesar los datos una vez al inicio"""
    try:
        
        shapefile_path = "data/MGN2021_DPTO_POLITICO/MGN_DPTO_POLITICO.shp"
        data = gpd.read_file(shapefile_path, encoding='utf-8')
        
        # Cargar datos de oficinas
        df = pd.read_csv("data/Oficinas_Fondo_Nacional_del_Ahorro_20250906.csv")
        
        # Procesamiento de datos
        df["departamentos"] = df["departamentos"].str.upper()
        df["departamentos"].replace(to_replace="HONDA", value="TOLIMA", inplace=True)
        
        # Crear DataFrame para unión espacial
        conteo_oficinas = df['departamentos'].value_counts().reset_index()
        conteo_oficinas.columns = ['departamento', 'cantidad_oficinas']
        
        # Estandarización de caracteres en shapefile
        caracteres_mal = ['Á', 'É', 'Í', 'Ó', 'Ú']  
        caracteres_bien = ['A', 'E', 'I', 'O', 'U'] 

        data["DPTO_CNMBR_NORM"] = data["DPTO_CNMBR"].copy()
        for j in range(len(caracteres_mal)):  
            data["DPTO_CNMBR_NORM"] = data["DPTO_CNMBR_NORM"].str.replace(caracteres_mal[j], caracteres_bien[j])
        
        # Corrección de nombres en el dataset
        mapeo_nombres = {
            'BOGOTA  D.C.': 'BOGOTA, D.C.',
            'BOGOTA D.C.': 'BOGOTA, D.C.',
            'GUAJIRA': 'LA GUAJIRA',
            'SAN ANDRES': 'ARCHIPIELAGO DE SAN ANDRES, PROVIDENCIA Y SANTA CATALINA',
            'NORTE DE SANTADER': 'NORTE DE SANTANDER', 
            'GUANIA': 'GUAINIA',
            'VALLE': 'VALLE DEL CAUCA'
        }
        
        conteo_oficinas['departamento_norm'] = conteo_oficinas['departamento'].replace(mapeo_nombres)
        
        # Unir datos
        data_unida = data.merge(conteo_oficinas, 
                               left_on='DPTO_CNMBR_NORM', 
                               right_on='departamento_norm', 
                               how='left')
        
        data_unida['cantidad_oficinas'] = data_unida['cantidad_oficinas'].fillna(0)
        
        return data_unida, df
        
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        # Retornar datos de ejemplo si hay error
        return create_sample_data(), pd.DataFrame()

def create_sample_data():
    """Crear datos de ejemplo si hay error con los archivos"""
    sample_data = {
        'DPTO_CNMBR': ['BOGOTA, D.C.', 'ANTIOQUIA', 'VALLE DEL CAUCA', 'CUNDINAMARCA', 
                      'SANTANDER', 'NARIÑO', 'TOLIMA', 'ATLANTICO', 'BOLIVAR', 'BOYACA'],
        'cantidad_oficinas': [20, 4, 4, 4, 3, 3, 3, 2, 2, 2],
        'geometry': [None] * 10
    }
    return pd.DataFrame(sample_data)

def create_folium_map(all_data, filtered_data, map_type):
    """Crear mapa Folium con sistema de dos capas"""
    mapa = folium.Map(location=[4.5709, -74.2973], zoom_start=5)
    
    # PRIMERA CAPA: Todos los departamentos en gris claro
    def base_style_function(feature):
        return {
            'fillColor': '#F7F7F7FF',
            'color': 'black',  
            'weight': 1.1,
            'fillOpacity': 0.6
        }
    
    folium.GeoJson(
        all_data,
        style_function=base_style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=['DPTO_CNMBR', 'cantidad_oficinas'],
            aliases=['Departamento: ', 'Oficinas: '],
            localize=True
        )
    ).add_to(mapa)
    
    # SEGUNDA CAPA: Solo departamentos filtrados con colores según el tipo de mapa
    if not filtered_data.empty and 'geometry' in filtered_data.columns and not filtered_data['geometry'].isnull().all():
        if map_type == 'thematic':
            # Mapa temático original con colores variados
            colores_ylorrd_compacta = ['#7CFC00', '#FFFF00', '#FFA500', '#FF0000', '#800080']
            valores_unicos = sorted(filtered_data['cantidad_oficinas'].unique())
            color_dict = {valor: colores_ylorrd_compacta[i % len(colores_ylorrd_compacta)] 
                         for i, valor in enumerate(valores_unicos)}
            
            def thematic_style_function(feature):
                cantidad = feature['properties']['cantidad_oficinas']
                return {
                    'fillColor': color_dict.get(cantidad, '#CCCCCC'),
                    'color': 'black',  
                    'weight': 1.1,
                    'fillOpacity': 0.6
                }
            
            style_function = thematic_style_function
            
        else:  # Mapa con escala de azules
            colores_azules = ["#9FBFFFFF", "#3E7DFBFF", "#0000FFE1", "#000080", '#FFFF00FF']
            valores_unicos = sorted(filtered_data['cantidad_oficinas'].unique())
            color_dict = {valor: colores_azules[i % len(colores_azules)] for i, valor in enumerate(valores_unicos)}
            
            def blues_style_function(feature):
                cantidad = feature['properties']['cantidad_oficinas']
                return {
                    'fillColor': color_dict.get(cantidad, '#CCCCCC'),
                    'color': 'black',  
                    'weight': 1.1,
                    'fillOpacity': 0.6
                }
            
            style_function = blues_style_function
        
        # Añadir la segunda capa con los datos filtrados
        folium.GeoJson(
            filtered_data,
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=['DPTO_CNMBR', 'cantidad_oficinas'],
                aliases=['Departamento: ', 'Oficinas: '],
                localize=True
            )
        ).add_to(mapa)
    
    return mapa

def create_top_departments_chart(data):
    """Crear gráfico de top 7 departamentos"""
    top_data = data.nlargest(7, 'cantidad_oficinas')
    
    # Colores específicos para cada categoría
    color_map = {
        20: '#800080',  # Morado para 20 oficinas
        4: '#FF0000',   # Rojo para 4 oficinas
        3: '#FFA500',   # Naranja para 3 oficinas
        2: '#FFFF00',   # Amarillo para 2 oficinas
        1: '#7CFC00'    # Verde para 1 oficina
    }
    
    # Asignar colores basados en la cantidad de oficinas
    colors = [color_map.get(x, '#CCCCCC') for x in top_data['cantidad_oficinas']]
    
    fig = px.bar(
        top_data,
        y='DPTO_CNMBR',
        x='cantidad_oficinas',
        orientation='h',
        title='',
        labels={'cantidad_oficinas': 'Número de Oficinas', 'DPTO_CNMBR': 'Departamento'}
    )
    
    fig.update_traces(
        marker_color=colors,
        marker_line_color='rgb(8,48,107)',
        marker_line_width=1.5
    )
    
    fig.update_layout(
        plot_bgcolor='white',
        yaxis={'categoryorder': 'total ascending'},
        height=400,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=False
    )
    
    return fig

def create_distribution_chart(data):
    """Crear gráfico de distribución"""
    dist_data = data['cantidad_oficinas'].value_counts().sort_index()
    
    # Colores específicos para el gráfico de torta
    colores_torta = ['#7CFC00', '#FFFF00', '#FFA500', '#FF0000', '#800080']
    
    fig = px.pie(
        values=dist_data.values,
        names=[f"{int(x)} oficina(s)" for x in dist_data.index],
        title='',
        color_discrete_sequence=colores_torta
    )
    
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label'
    )
    
    fig.update_layout(
        height=400,
        showlegend=False,
        margin=dict(l=20, r=20, t=20, b=20)
    )
    
    return fig

def style_dataframe(row):
    """Función corregida para aplicar estilos a cada fila"""
    if row['cantidad_oficinas'] >= 4:
        return ['background-color: #e8f5e8', 'background-color: #e8f5e8']
    elif row['cantidad_oficinas'] == 3:
        return ['background-color: #fff3cd', 'background-color: #fff3cd']
    elif row['cantidad_oficinas'] == 2:
        return ['background-color: #ffeaa7', 'background-color: #ffeaa7']
    else:
        return ['background-color: #f8f9fa', 'background-color: #f8f9fa']

def main():
    # Header principal
    st.markdown("""
    <div class="main-header">
        <div style="max-width: 1200px; margin: 0 auto; text-align: center;">
            <h1 style="color: white; margin-bottom: 10px;">Análisis de la Red de Oficinas del Fondo Nacional del Ahorro</h1>
            <p style="color: white; margin-bottom: 0px; font-size: 18px;">Dashboard interactivo - Distribución territorial de oficinas en Colombia</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Cargar datos
    data_unida_global, df_global = load_and_process_data()
    
    # Pestañas
    tab1, tab2, tab3 = st.tabs(["📋 Contexto y Metodología", "📊 Análisis Visual", "📈 Conclusiones"])
    
    with tab1:
        st.markdown("""
        <div class="section-card">
            <h2 style="color: #2c3e50; margin-bottom: 20px; text-align: center;">Contexto del Estudio</h2>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        El presente informe analiza la estructura y distribución de la red de oficinas del **Fondo Nacional del Ahorro (FNA)**, 
        institución de carácter oficial que cumple una función fundamental en el sistema de ahorro y crédito para vivienda en Colombia. 
        Los datos utilizados en este estudio, actualizados al **25 de agosto de 2025**, fueron proporcionados oficialmente por el 
        Fondo Nacional del Ahorro a través del portal de datos abiertos del Gobierno Colombiano en 
        [datos.gov.co](https://www.datos.gov.co/Vivienda-Ciudad-y-Territorio/Oficinas-Fondo-Nacional-del-Ahorro/h3sz-zqij/about_data).
        """)
        
        st.markdown("""
        El conjunto de datos constituye un registro completo de la infraestructura física de atención al público del FNA, donde cada 
        registro representa una **sede u oficina operativa** de la entidad en el territorio nacional. Esta información es de vital 
        importancia para comprender la capacidad institucional de cobertura, el acceso a servicios financieros de vivienda por parte 
        de la ciudadanía y la presencia territorial de una de las entidades más importantes del sector.
        """)
        
        st.markdown("""
        La disponibilidad de estos datos mediante la política de **Gobierno Abierto** implementada por el Gobierno de Colombia, 
        refleja el compromiso del Estado con la transparencia y la rendición de cuentas, permitiendo a ciudadanos, investigadores 
        y tomadores de decisiones realizar análisis basados en evidencia sobre la prestación de servicios públicos.
        """)
        
        st.markdown("### Metodología")
        st.markdown("""
        - Fuente de datos: Portal de Datos Abiertos de Colombia (datos.gov.co)
        - Shapefile: Departamento Administrativo Nacional de Estadística (DANE)
        - Procesamiento: Python con Pandas, GeoPandas y Folium
        - Visualización: Streamlit y Plotly para interactividad
        """)
        
        st.markdown("### Objetivos del Análisis")
        st.markdown("""
        - Identificar patrones de distribución territorial de las oficinas del FNA
        - Analizar desigualdades regionales en la cobertura de servicios
        - Visualizar la concentración geográfica de la infraestructura financiera
        - Proporcionar insights para políticas públicas de inclusión financiera
        """)
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    with tab2:
        if data_unida_global is not None and not data_unida_global.empty:
            # Estadísticas clave
            col1, col2, col3, col4 = st.columns(4)
            
            total_oficinas = int(df_global.shape[0]) if not df_global.empty else 71
            total_departamentos = len(data_unida_global[data_unida_global['cantidad_oficinas'] > 0])
            max_oficinas = int(data_unida_global['cantidad_oficinas'].max())
            min_oficinas = int(data_unida_global[data_unida_global['cantidad_oficinas'] > 0]['cantidad_oficinas'].min())
            
            with col1:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 2.5rem; font-weight: bold; color: #2c3e50;">{total_oficinas}</div>
                    <div style="font-size: 1rem; color: #7f8c8d;">Total Oficinas</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 2.5rem; font-weight: bold; color: #2c3e50;">{total_departamentos}</div>
                    <div style="font-size: 1rem; color: #7f8c8d;">Departamentos con Cobertura</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 2.5rem; font-weight: bold; color: #2c3e50;">{min_oficinas}</div>
                    <div style="font-size: 1rem; color: #7f8c8d;">Mín. Oficinas por Depto</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 2.5rem; font-weight: bold; color: #2c3e50;">{max_oficinas}</div>
                    <div style="font-size: 1rem; color: #7f8c8d;">Máx. Oficinas por Depto</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Filtros en sidebar
            st.sidebar.header("Controles de Visualización")
            
            map_type = st.sidebar.selectbox(
                "Tipo de Mapa:",
                options=['🎨 Mapa Temático (Escala de Colores)', '🔵 Mapa Temático (Escala de Azules)'],
                index=0
            )
            
            map_type_value = 'thematic' if 'Colores' in map_type else 'blues'
            
            office_range = st.sidebar.slider(
                "Filtrar por Número de Oficinas:",
                min_value=1,
                max_value=20,
                value=(1, 20),
                step=1
            )
            
            region_options = sorted(data_unida_global['DPTO_CNMBR_NORM'].unique())
            selected_regions = st.sidebar.multiselect(
                "Filtrar por Región:",
                options=region_options,
                placeholder="Seleccione regiones..."
            )
            
            if st.sidebar.button("🔄 Resetear Filtros"):
                st.rerun()
            
            # Aplicar filtros
            filtered_data = data_unida_global.copy()
            
            if selected_regions:
                filtered_data = filtered_data[filtered_data['DPTO_CNMBR_NORM'].isin(selected_regions)]
            
            filtered_data = filtered_data[
                (filtered_data['cantidad_oficinas'] >= office_range[0]) & 
                (filtered_data['cantidad_oficinas'] <= office_range[1])
            ]
            
            # Mapa y controles 
            col_map, col_info = st.columns([70, 30])
            
            with col_map:
                st.markdown("""
                <div class="section-card">
                    <div class="section-header">Distribución Geográfica de Oficinas</div>
                    <div style="padding: 1rem;">
                """, unsafe_allow_html=True)
                
                mapa = create_folium_map(data_unida_global, filtered_data, map_type_value)
                st_folium(mapa, width=None, height=500, use_container_width=True)
                
                st.markdown("</div></div>", unsafe_allow_html=True)
            
            with col_info:
                st.markdown("""
                <div class="section-card">
                    <div class="section-header">Leyenda del Mapa</div>
                    <div style="padding: 1.5rem;">
                        <p><strong>Cantidad de Oficinas:</strong></p>
                        <p>🟢 1 oficina<br>
                        🟡 2 oficinas<br>
                        🟠 3 oficinas<br>
                        🔴 4 oficinas<br>
                        🟣 20 oficinas (Bogotá)<br>
                        ⚪ Otros departamentos</p>
                        <p style="margin-top: 20px; font-size: 0.9rem; color: #666;">
                        <em>Use los controles en el sidebar para filtrar los datos del mapa.</em>
                        </p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            # Gráficos 
            st.markdown('<div style="margin-top: 2rem;">', unsafe_allow_html=True)
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.markdown("""
                <div class="section-card">
                    <div class="section-header">Top 7 Departamentos con Más Oficinas</div>
                    <div style="padding: 1rem;">
                """, unsafe_allow_html=True)
                top_chart = create_top_departments_chart(data_unida_global)
                st.plotly_chart(top_chart, use_container_width=True)
                st.markdown("</div></div>", unsafe_allow_html=True)
            
            with col_chart2:
                st.markdown("""
                <div class="section-card">
                    <div class="section-header">Distribución por Número de Oficinas</div>
                    <div style="padding: 1rem;">
                """, unsafe_allow_html=True)
                dist_chart = create_distribution_chart(data_unida_global)
                st.plotly_chart(dist_chart, use_container_width=True)
                st.markdown("</div></div>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Tabla de datos
            st.markdown("""
            <div class="section-card">
                <div class="section-header">📋 Detalle de Oficinas por Departamento</div>
                <div style="padding: 1rem;">
            """, unsafe_allow_html=True)
            
            table_data = data_unida_global[['DPTO_CNMBR', 'cantidad_oficinas']].sort_values('cantidad_oficinas', ascending=False)
            
            # Aplicar estilos a la tabla
            styled_df = table_data.style.apply(style_dataframe, axis=1)
            
            st.dataframe(styled_df, width='stretch', height=400)
            
            st.markdown("</div></div>", unsafe_allow_html=True)
        
        else:
            st.error("No se pudieron cargar los datos. Verifique que los archivos estén en la carpeta 'data/'")
    
    with tab3:
        st.markdown("""
        <div class="section-card">
            <h2 style="color: #2c3e50; margin-bottom: 25px; text-align: center;">
                Interpretación de los Resultados y Conclusiones
            </h2>
        """, unsafe_allow_html=True)
        

        st.markdown("### Distribución de Oficinas del Fondo Nacional del Ahorro por Departamento")
        
        st.markdown("#### Regiones con Valores Más Altos:")
        st.markdown("""
        - **Bogotá D.C. domina ampliamente** con 20 oficinas, concentrando el mayor número a nivel nacional.
        - **Región Andina Central**: Departamentos como Cundinamarca, Antioquia y Valle del Cauca presentan 4 oficinas cada uno, mostrando una presencia significativa.
        - **Zonas Intermedias**: Tolima, Santander y Nariño tienen 3 oficinas cada uno, indicando una cobertura media-alta.
        """)
        
        st.markdown("#### Desigualdades Territoriales Evidentes:")
        st.markdown("""
        - **Disparidad Extrema**: Bogotá tiene 20 veces más oficinas que la mayoría de departamentos (que solo tienen 1).
        - **Centralismo Marcado**: La región central (Andina) concentra la mayoría de oficinas, mientras que:
            - Región Caribe: Ningún departamento supera las 2 oficinas
            - Región Pacífica: Chocó y Cauca solo tienen 1 oficina cada uno
            - Región Amazónica: Amazonas, Guainía, Guaviare, Vaupés tienen solo 1 oficina para vastos territorios
            - Región Orinoquía: Arauca, Casanare, Vichada con apenas 1 oficina cada uno
        """)
        
        st.markdown("#### Factores Explicativos de las Diferencias:")
        
        st.markdown("##### Factores Demográficos y Económicos:")
        st.markdown("""
        - Densidad Poblacional: Bogotá y departamentos andinos tienen mayor población
        - Desarrollo Económico: Regiones con mayor actividad económica demandan más servicios financieros
        - Urbanización: Áreas urbanas concentran mayor demanda de créditos de vivienda
        """)
        
        st.markdown("##### Factores Geográficos y Logísticos:")
        st.markdown("""
        - Accesibilidad: Departamentos remotos (Amazonas, Guainía) presentan desafíos de conectividad
        - Extensión Territorial: Departamentos grandes con baja densidad (Vichada, Guaviare) tienen menor cobertura
        """)
        
        st.markdown("##### Factores Institucionales y Históricos:")
        st.markdown("""
        - Enfoque de Mercado: Priorización de zonas con mayor potencial de cartera
        - Infraestructura Existente: Limitaciones en instalación de oficinas en zonas periféricas
        """)
        
        # Conclusión Principal
        st.markdown("---")
        st.markdown("#### Conclusión Principal")
        st.info("""
        **"La distribución refleja patrones históricos de desarrollo desigual en Colombia, donde las regiones centrales 
        concentran la infraestructura financiera mientras las periféricas enfrentan limitaciones de acceso."**
        """)
        
        st.markdown("---")
        st.markdown("### La Georreferenciación como Herramienta Clave para el Análisis Social")
        
        st.markdown("""
        El análisis georreferenciado de la distribución de oficinas del Fondo Nacional del Ahorro evidencia la 
        **capacidad transformadora de los datos espaciales** en estudios sociales. La visualización espacial no solo permite identificar patrones geográficos de concentración y exclusión, sino que 
        **revela dimensiones críticas del desarrollo territorial** que pasarían desapercibidas en análisis tabulares convencionales.
        """)
        
        st.markdown("""
        La georreferenciación **materializa las desigualdades**, transformando datos abstractos en realidades tangibles: muestra cómo el centralismo bogotano se impone sobre las periferias, cómo la región Caribe a pesar de su extensión y población mantiene una cobertura marginal, y cómo la Amazonia y Orinoquia enfrentan desafíos de inclusión financiera proporcionales a su vastedad territorial.
        """)
        
        st.markdown("""
        Este ejercicio demuestra que **la geografía no es solo un contenedor de fenómenos sociales, sino un factor activo** que configura oportunidades de acceso. La disposición espacial de la infraestructura financiera refleja y, a la vez, reproduce dinámicas de desarrollo desigual, haciendo evidente la 
        **necesidad de políticas públicas con enfoque territorial diferenciado**.
        """)
        
        st.markdown("#### Aportes de la Georreferenciación para la Equidad")
        st.markdown("""
        - Identificar brechas de cobertura con precisión
        - Priorizar inversiones en territorios históricamente marginados  
        - Diseñar estrategias adaptadas a las realidades regionales
        - Evaluar impactos de políticas con dimensión espacial
        """)
        
        st.markdown("</div>", unsafe_allow_html=True)

if __name__ == '__main__':
    main()