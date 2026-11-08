import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "prototipo-academico")
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "produccion.db")
ESTADOS = ["Pendiente", "En proceso", "Terminada"]
ROLES = ["admin", "jefe", "inventario", "operario"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios(id INTEGER PRIMARY KEY, nombre TEXT, usuario TEXT UNIQUE, clave TEXT, rol TEXT);
CREATE TABLE IF NOT EXISTS productos(id INTEGER PRIMARY KEY, codigo TEXT UNIQUE, nombre TEXT, descripcion TEXT, terminados INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS materias(id INTEGER PRIMARY KEY, nombre TEXT, unidad TEXT, existencias REAL, minimo REAL);
CREATE TABLE IF NOT EXISTS ordenes(id INTEGER PRIMARY KEY, producto_id INTEGER, cantidad INTEGER, estado TEXT, fecha TEXT, responsable TEXT);
"""


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def cerrar(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def q(sql, args=(), one=False):
    cur = db().execute(sql, args)
    datos = cur.fetchone() if one else cur.fetchall()
    db().commit()
    return datos


def init_db():
    with sqlite3.connect(DB) as c:
        c.executescript(SCHEMA)
        if not c.execute("SELECT 1 FROM usuarios").fetchone():
            for n, u, r in [("Administrador", "admin", "admin"), ("Jefe de producción", "jefe", "jefe"),
                            ("Encargado de inventario", "inventario", "inventario"), ("Operario", "operario", "operario")]:
                c.execute("INSERT INTO usuarios(nombre,usuario,clave,rol) VALUES(?,?,?,?)",
                          (n, u, generate_password_hash(u + "123"), r))
            c.executemany("INSERT INTO productos(codigo,nombre,descripcion) VALUES(?,?,?)",
                          [("P-001", "Soporte metálico", "Soporte en ángulo de acero 3 mm"),
                           ("P-002", "Reja de seguridad", "Reja soldada para ventana")])
            c.executemany("INSERT INTO materias(nombre,unidad,existencias,minimo) VALUES(?,?,?,?)",
                          [("Lámina de acero", "kg", 120, 50), ("Varilla corrugada", "m", 30, 40), ("Electrodos", "kg", 15, 5)])


def acceso(*roles):
    def deco(f):
        @wraps(f)
        def interno(*a, **k):
            if "rol" not in session:
                return redirect(url_for("login"))
            if roles and session["rol"] not in roles:
                flash("Tu rol no tiene permiso para esta acción.", "error")
                return redirect(url_for("productos"))
            return f(*a, **k)
        return interno
    return deco


@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = q("SELECT * FROM usuarios WHERE usuario=?", (request.form["usuario"].strip(),), one=True)
        if u and check_password_hash(u["clave"], request.form["clave"]):
            session.update(rol=u["rol"], nombre=u["nombre"])
            return redirect(url_for("productos"))
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Productos ----------
@app.route("/productos")
@acceso()
def productos():
    return render_template("productos.html", datos=q("SELECT * FROM productos ORDER BY codigo"),
                           edita=session["rol"] in ("admin", "jefe"))


@app.route("/productos/nuevo", methods=["GET", "POST"])
@app.route("/productos/<int:pid>/editar", methods=["GET", "POST"])
@acceso("admin", "jefe")
def producto_form(pid=None):
    p = q("SELECT * FROM productos WHERE id=?", (pid,), one=True) if pid else None
    if request.method == "POST":
        f = request.form
        if not f["codigo"].strip() or not f["nombre"].strip():
            flash("El código y el nombre son obligatorios.", "error")
        else:
            try:
                if pid:
                    q("UPDATE productos SET codigo=?,nombre=?,descripcion=? WHERE id=?",
                      (f["codigo"].strip(), f["nombre"].strip(), f["descripcion"].strip(), pid))
                else:
                    q("INSERT INTO productos(codigo,nombre,descripcion) VALUES(?,?,?)",
                      (f["codigo"].strip(), f["nombre"].strip(), f["descripcion"].strip()))
                flash("Producto guardado.", "ok")
                return redirect(url_for("productos"))
            except sqlite3.IntegrityError:
                flash("Ya existe un producto con ese código.", "error")
    return render_template("producto_form.html", p=p)


@app.route("/productos/<int:pid>/eliminar", methods=["POST"])
@acceso("admin", "jefe")
def producto_eliminar(pid):
    if q("SELECT 1 FROM ordenes WHERE producto_id=?", (pid,), one=True):
        flash("No se puede eliminar: el producto tiene órdenes de producción.", "error")
    else:
        q("DELETE FROM productos WHERE id=?", (pid,))
        flash("Producto eliminado.", "ok")
    return redirect(url_for("productos"))


# ---------- Materias primas ----------
@app.route("/materias", methods=["GET", "POST"])
@acceso()
def materias():
    edita = session["rol"] in ("admin", "inventario")
    if request.method == "POST":
        if not edita:
            flash("Tu rol no tiene permiso para esta acción.", "error")
        else:
            f = request.form
            try:
                q("INSERT INTO materias(nombre,unidad,existencias,minimo) VALUES(?,?,?,?)",
                  (f["nombre"].strip(), f["unidad"].strip(), float(f["existencias"]), float(f["minimo"])))
                flash("Materia prima registrada.", "ok")
            except ValueError:
                flash("Las existencias y el mínimo deben ser números.", "error")
        return redirect(url_for("materias"))
    return render_template("materias.html", datos=q("SELECT * FROM materias ORDER BY nombre"), edita=edita)


@app.route("/materias/<int:mid>/existencias", methods=["POST"])
@acceso("admin", "inventario")
def materia_existencias(mid):
    try:
        q("UPDATE materias SET existencias=? WHERE id=?", (float(request.form["existencias"]), mid))
        flash("Existencias actualizadas.", "ok")
    except ValueError:
        flash("Las existencias deben ser un número.", "error")
    return redirect(url_for("materias"))


# ---------- Órdenes de producción ----------
@app.route("/ordenes", methods=["GET", "POST"])
@acceso()
def ordenes():
    crea = session["rol"] in ("admin", "jefe")
    if request.method == "POST":
        if not crea:
            flash("Tu rol no tiene permiso para esta acción.", "error")
        elif not request.form["cantidad"].isdigit() or int(request.form["cantidad"]) < 1:
            flash("La cantidad debe ser un número entero mayor que cero.", "error")
        else:
            q("INSERT INTO ordenes(producto_id,cantidad,estado,fecha,responsable) VALUES(?,?,?,?,?)",
              (request.form["producto_id"], int(request.form["cantidad"]), "Pendiente",
               datetime.now().strftime("%Y-%m-%d %H:%M"), session["nombre"]))
            flash("Orden registrada.", "ok")
        return redirect(url_for("ordenes"))
    datos = q("SELECT o.*, p.nombre AS producto FROM ordenes o JOIN productos p ON p.id=o.producto_id ORDER BY o.id DESC")
    return render_template("ordenes.html", datos=datos, prods=q("SELECT * FROM productos ORDER BY nombre"),
                           estados=ESTADOS, crea=crea)


@app.route("/ordenes/<int:oid>/estado", methods=["POST"])
@acceso("admin", "jefe", "operario")
def orden_estado(oid):
    o = q("SELECT * FROM ordenes WHERE id=?", (oid,), one=True)
    nuevo = request.form["estado"]
    if not o or nuevo not in ESTADOS:
        flash("Estado no válido.", "error")
    elif o["estado"] == "Terminada":
        flash("Una orden terminada ya no se puede modificar.", "error")
    else:
        q("UPDATE ordenes SET estado=? WHERE id=?", (nuevo, oid))
        if nuevo == "Terminada":  # registra los productos terminados
            q("UPDATE productos SET terminados=terminados+? WHERE id=?", (o["cantidad"], o["producto_id"]))
        flash("Estado actualizado.", "ok")
    return redirect(url_for("ordenes"))


# ---------- Reportes y usuarios ----------
@app.route("/reportes")
@acceso("admin", "jefe")
def reportes():
    por_estado = {e: q("SELECT COUNT(*) c FROM ordenes WHERE estado=?", (e,), one=True)["c"] for e in ESTADOS}
    return render_template("reportes.html", por_estado=por_estado,
                           bajas=q("SELECT * FROM materias WHERE existencias < minimo"),
                           prods=q("SELECT * FROM productos ORDER BY terminados DESC"))


@app.route("/usuarios", methods=["GET", "POST"])
@acceso("admin")
def usuarios():
    if request.method == "POST":
        f = request.form
        if not f["usuario"].strip() or len(f["clave"]) < 6 or f["rol"] not in ROLES:
            flash("Completa los datos; la contraseña debe tener al menos 6 caracteres.", "error")
        else:
            try:
                q("INSERT INTO usuarios(nombre,usuario,clave,rol) VALUES(?,?,?,?)",
                  (f["nombre"].strip(), f["usuario"].strip(), generate_password_hash(f["clave"]), f["rol"]))
                flash("Usuario creado.", "ok")
            except sqlite3.IntegrityError:
                flash("Ese nombre de usuario ya existe.", "error")
        return redirect(url_for("usuarios"))
    return render_template("usuarios.html", datos=q("SELECT * FROM usuarios"), roles=ROLES)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
