# Sistema web de gestión de producción

Prototipo funcional para el control de producción de una empresa metalmecánica.
Proyecto académico de **Proyecto de software**. Autor: Robinson Damian Rodríguez Rodríguez.
Corporación Universitaria Iberoamericana, Ingeniería de Software, Bogotá D.C.

## Requisitos
- Python 3.9 o superior

## Instalación y ejecución
```bash
git clone https://github.com/robin4550/sistema-gestion-produccion.git
cd sistema-gestion-produccion
python -m venv venv
venv\Scripts\activate        # En Linux o macOS: source venv/bin/activate
pip install -r requirements.txt
python app.py
```
Abre http://127.0.0.1:5000 en el navegador. La base de datos SQLite se crea sola con datos de ejemplo.

## Usuarios de prueba
| Usuario | Contraseña | Rol |
|---|---|---|
| admin | admin123 | Administrador |
| jefe | jefe123 | Jefe de producción |
| inventario | inventario123 | Encargado de inventario |
| operario | operario123 | Operario |

## Funcionalidades
Inicio de sesión con roles, CRUD de productos, materias primas con alerta de mínimo, órdenes de producción con cambio de estado (al terminar una orden se suman los productos terminados), reportes básicos y administración de usuarios.
