import sys
import sqlite3
import requests
import logging
from datetime import datetime
import json
import pandas as pd

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, 
    QTabWidget, QMessageBox, QFileDialog, QComboBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon

class RegistroSaludChile:
    def __init__(self, db_name='registro_salud.db'):
        """
        Inicializa la base de datos SQLite y configura la conexión con la API
        """
        self.api_base_url = 'https://apis.superdesalud.gob.cl/api/prestadores/rut/'
        self.api_key = '7bb3a137836b753e64b375fccaad02998edad948'
        
        self.conn = sqlite3.connect(db_name)
        self.crear_tablas()

    def crear_tablas(self):
        """
        Crea las tablas necesarias para prestadores
        """
        cursor = self.conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS prestadores (
            rut TEXT PRIMARY KEY,
            nombre TEXT,
            apellido TEXT,
            profesion TEXT,
            especialidad TEXT,
            registro_superintendencia TEXT,
            estado_registro TEXT,
            fecha_registro TEXT,
            datos_completos TEXT
        )
        ''')
        
        self.conn.commit()

    def obtener_datos_prestador(self, rut: str):
        """
        Obtiene datos de un prestador desde la API de SuperSalud
        """
        rut_formateado = rut.replace('.', '').replace('-', '')
        url = f"{self.api_base_url}{rut_formateado}.json/?apikey={self.api_key}"
        
        try:
            respuesta = requests.get(url, timeout=10)
            
            if respuesta.status_code == 200:
                return respuesta.json()
            else:
                return None
        
        except requests.RequestException:
            return None

    def registrar_prestador(self, rut: str):
        """
        Registra un prestador en la base de datos local
        """
        datos_api = self.obtener_datos_prestador(rut)
        
        if not datos_api:
            return False
        
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT OR REPLACE INTO prestadores 
            (rut, nombre, apellido, profesion, especialidad, 
             registro_superintendencia, estado_registro, 
             fecha_registro, datos_completos) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                rut,
                datos_api.get('nombre', ''),
                datos_api.get('apellido', ''),
                datos_api.get('profesion', ''),
                datos_api.get('especialidad', ''),
                datos_api.get('registro_superintendencia', ''),
                datos_api.get('estado', 'No especificado'),
                datetime.now().isoformat(),
                json.dumps(datos_api)
            ))
            self.conn.commit()
            return True
        
        except Exception:
            return False

    def buscar_prestadores(self, filtro=None):
        """
        Busca prestadores según criterios específicos
        """
        cursor = self.conn.cursor()
        query = "SELECT * FROM prestadores WHERE 1=1"
        params = []

        if filtro:
            if filtro.get('profesion'):
                query += " AND profesion LIKE ?"
                params.append(f"%{filtro['profesion']}%")
            
            if filtro.get('especialidad'):
                query += " AND especialidad LIKE ?"
                params.append(f"%{filtro['especialidad']}%")
            
            if filtro.get('estado_registro'):
                query += " AND estado_registro = ?"
                params.append(filtro['estado_registro'])

        cursor.execute(query, params)
        return cursor.fetchall()

class ThreadObtenerPrestador(QThread):
    """
    Thread para obtener datos de prestador sin bloquear la interfaz
    """
    datos_obtenidos = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, registro, rut):
        super().__init__()
        self.registro = registro
        self.rut = rut

    def run(self):
        datos = self.registro.obtener_datos_prestador(self.rut)
        
        if datos:
            self.datos_obtenidos.emit(datos)
        else:
            self.error.emit("No se pudieron obtener los datos del prestador")

class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.registro = RegistroSaludChile()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Registro de Prestadores de Salud')
        self.setGeometry(100, 100, 1000, 600)
        
        # Widget central y layout principal
        widget_central = QWidget()
        layout_principal = QVBoxLayout()
        widget_central.setLayout(layout_principal)
        self.setCentralWidget(widget_central)

        # Crear pestañas
        tabs = QTabWidget()
        
        # Pestaña de Registro de Prestadores
        tab_registro = QWidget()
        layout_registro = QVBoxLayout()
        tab_registro.setLayout(layout_registro)

        # Input para RUT
        layout_rut = QHBoxLayout()
        label_rut = QLabel('RUT del Prestador:')
        self.input_rut = QLineEdit()
        boton_buscar = QPushButton('Buscar')
        boton_buscar.clicked.connect(self.buscar_prestador)
        
        layout_rut.addWidget(label_rut)
        layout_rut.addWidget(self.input_rut)
        layout_rut.addWidget(boton_buscar)
        
        # Tabla de resultados
        self.tabla_resultados = QTableWidget()
        self.tabla_resultados.setColumnCount(6)
        self.tabla_resultados.setHorizontalHeaderLabels([
            'RUT', 'Nombre', 'Profesión', 'Especialidad', 
            'Estado Registro', 'Fecha Registro'
        ])

        # Opciones de búsqueda avanzada
        layout_filtros = QHBoxLayout()
        
        label_profesion = QLabel('Profesión:')
        self.input_profesion = QLineEdit()
        
        label_especialidad = QLabel('Especialidad:')
        self.input_especialidad = QLineEdit()
        
        label_estado = QLabel('Estado:')
        self.combo_estado = QComboBox()
        self.combo_estado.addItems([
            'Todos', 
            'Activo', 
            'Suspendido', 
            'No especificado'
        ])
        
        boton_buscar_avanzado = QPushButton('Buscar Avanzado')
        boton_buscar_avanzado.clicked.connect(self.buscar_prestadores_avanzado)
        boton_exportar = QPushButton('Exportar CSV')
        boton_exportar.clicked.connect(self.exportar_csv)
        
        layout_filtros.addWidget(label_profesion)
        layout_filtros.addWidget(self.input_profesion)
        layout_filtros.addWidget(label_especialidad)
        layout_filtros.addWidget(self.input_especialidad)
        layout_filtros.addWidget(label_estado)
        layout_filtros.addWidget(self.combo_estado)
        layout_filtros.addWidget(boton_buscar_avanzado)
        layout_filtros.addWidget(boton_exportar)

        # Agregar widgets al layout de registro
        layout_registro.addLayout(layout_rut)
        layout_registro.addLayout(layout_filtros)
        layout_registro.addWidget(self.tabla_resultados)

        # Agregar pestaña de registro a las pestañas
        tabs.addTab(tab_registro, "Registro de Prestadores")

        # Agregar pestañas al layout principal
        layout_principal.addWidget(tabs)

    def buscar_prestador(self):
        rut = self.input_rut.text()
        
        # Iniciar thread para búsqueda
        self.thread_prestador = ThreadObtenerPrestador(self.registro, rut)
        self.thread_prestador.datos_obtenidos.connect(self.mostrar_datos_prestador)
        self.thread_prestador.error.connect(self.mostrar_error)
        self.thread_prestador.start()

    def mostrar_datos_prestador(self, datos):
        # Registrar prestador
        self.registro.registrar_prestador(self.input_rut.text())
        
        # Limpiar tabla
        self.tabla_resultados.setRowCount(0)
        
        # Agregar fila
        row_position = self.tabla_resultados.rowCount()
        self.tabla_resultados.insertRow(row_position)
        
        # Agregar datos
        self.tabla_resultados.setItem(row_position, 0, QTableWidgetItem(self.input_rut.text()))
        self.tabla_resultados.setItem(row_position, 1, QTableWidgetItem(f"{datos.get('nombre', '')} {datos.get('apellido', '')}"))
        self.tabla_resultados.setItem(row_position, 2, QTableWidgetItem(datos.get('profesion', '')))
        self.tabla_resultados.setItem(row_position, 3, QTableWidgetItem(datos.get('especialidad', '')))
        self.tabla_resultados.setItem(row_position, 4, QTableWidgetItem(datos.get('estado', 'No especificado')))
        self.tabla_resultados.setItem(row_position, 5, QTableWidgetItem(datetime.now().strftime('%Y-%m-%d')))

    def mostrar_error(self, mensaje):
        QMessageBox.warning(self, 'Error', mensaje)

    def buscar_prestadores_avanzado(self):
        filtro = {}
        
        profesion = self.input_profesion.text()
        especialidad = self.input_especialidad.text()
        estado = self.combo_estado.currentText()
        
        if profesion:
            filtro['profesion'] = profesion
        if especialidad:
            filtro['especialidad'] = especialidad
        if estado != 'Todos':
            filtro['estado_registro'] = estado
        
        resultados = self.registro.buscar_prestadores(filtro)
        
        # Limpiar tabla
        self.tabla_resultados.setRowCount(0)
        
        # Agregar resultados
        for resultado in resultados:
            row_position = self.tabla_resultados.rowCount()
            self.tabla_resultados.insertRow(row_position)
            
            self.tabla_resultados.setItem(row_position, 0, QTableWidgetItem(resultado[0]))  # RUT
            self.tabla_resultados.setItem(row_position, 1, QTableWidgetItem(f"{resultado[1]} {resultado[2]}"))  # Nombre
            self.tabla_resultados.setItem(row_position, 2, QTableWidgetItem(resultado[3]))  # Profesión
            self.tabla_resultados.setItem(row_position, 3, QTableWidgetItem(resultado[4]))  # Especialidad
            self.tabla_resultados.setItem(row_position, 4, QTableWidgetItem(resultado[6]))  # Estado
            self.tabla_resultados.setItem(row_position, 5, QTableWidgetItem(resultado[7]))  # Fecha

    def exportar_csv(self):
        # Obtener ruta para guardar
        ruta, _ = QFileDialog.getSaveFileName(self, 'Exportar CSV', '', 'Archivos CSV (*.csv)')
        
        if ruta:
            # Exportar datos de la tabla
            try:
                num_columnas = self.tabla_resultados.columnCount()
                num_filas = self.tabla_resultados.rowCount()
                
                # Preparar datos
                datos = []
                encabezados = [self.tabla_resultados.horizontalHeaderItem(col).text() for col in range(num_columnas)]
                datos.append(encabezados)
                
                for fila in range(num_filas):
                    fila_datos = []
                    for columna in range(num_columnas):
                        item = self.tabla_resultados.item(fila, columna)
                        fila_datos.append(item.text() if item else '')
                    datos.append(fila_datos)
                
                # Convertir a DataFrame y exportar
                df = pd.DataFrame(datos[1:], columns=datos[0])
                df.to_csv(ruta, index=False)
                
                QMessageBox.information(self, 'Éxito', f'Datos exportados a {ruta}')
            
            except Exception as e:
                QMessageBox.warning(self, 'Error', f'No se pudo exportar: {str(e)}')

def main():
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
