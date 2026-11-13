const API = "/api";

let productosCache = [];
let tercerosCache = [];
let usuariosCache = [];

const money = (v) =>
  new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(Number(v || 0));

function mostrarAlerta(msg, tipo = "ok") {
  const el = document.getElementById("alerta");
  el.textContent = msg;
  el.className = `alerta ${tipo}`;
  setTimeout(() => {
    el.className = "alerta hidden";
  }, 5000);
}

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || data.error_db || "Error en la solicitud");
  }
  return data;
}

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".section").forEach((s) => s.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`sec-${btn.dataset.section}`).classList.add("active");
  });
});

async function cargarCatalogos() {
  const [prods, tercs, usrs] = await Promise.all([
    fetchJSON(`${API}/productos`),
    fetchJSON(`${API}/terceros`),
    fetchJSON(`${API}/usuarios`),
  ]);
  productosCache = prods;
  tercerosCache = tercs;
  usuariosCache = usrs;

  document.getElementById("kpi-productos").textContent = prods.length;
  document.getElementById("kpi-terceros").textContent = tercs.length;

  llenarSelect("venta-tercero", tercs, "id_tercero", "nombre");
  llenarSelect("pedido-tercero", tercs, "id_tercero", "nombre");
  llenarSelect("venta-usuario", usrs, "id_usuario", "nombre");
  llenarSelect("pedido-usuario", usrs, "id_usuario", "nombre");
}

function llenarSelect(id, lista, valKey, labelKey) {
  const sel = document.getElementById(id);
  const prev = sel.value;
  sel.innerHTML = lista.map((x) => `<option value="${x[valKey]}">${x[labelKey]}</option>`).join("");
  if (prev && lista.some((x) => String(x[valKey]) === prev)) sel.value = prev;
}

function crearFilaItem(tipo) {
  const cont = document.getElementById(`${tipo}-items`);
  const row = document.createElement("div");
  row.className = "item-row";

  const listaOpciones =
    tipo === "venta"
      ? [...productosCache].sort((a, b) => Number(b.cantidad_stock) - Number(a.cantidad_stock))
      : productosCache;

  const opciones = listaOpciones
    .map((p) => {
      const sinStock = tipo === "venta" && Number(p.cantidad_stock) <= 0;
      return `<option value="${p.id_producto}" data-compra="${p.precioCompra}" data-venta="${p.precioVenta}" data-iva="${p.tarifa_iva}" data-stock="${p.cantidad_stock}" ${sinStock ? "disabled" : ""}>${p.nombre} (Stock: ${p.cantidad_stock}${sinStock ? " - Sin stock" : ""})</option>`;
    })
    .join("");

  row.innerHTML = `
    <label>Producto
      <select class="item-prod" required>${opciones}</select>
    </label>
    <label>Cantidad
      <input type="number" class="item-cant" value="1" min="1" required />
    </label>
    <label>Precio Unitario
      <input type="number" class="item-precio" min="0" step="0.01" required />
    </label>
    <label>IVA
      <input type="number" class="item-iva" value="0.19" min="0" max="1" step="0.01" required />
    </label>
    <button type="button" class="btn btn-danger btn-sm btn-remove">Quitar</button>
  `;

  const sel = row.querySelector(".item-prod");
  const precioInput = row.querySelector(".item-precio");
  const ivaInput = row.querySelector(".item-iva");

  const syncPrecio = () => {
    const opt = sel.selectedOptions[0];
    if (!opt) return;
    precioInput.value = tipo === "venta" ? opt.dataset.venta : opt.dataset.compra;
    ivaInput.value = opt.dataset.iva || "0.19";
    recalcularTotal(tipo);
  };

  sel.addEventListener("change", syncPrecio);
  row.querySelectorAll("input").forEach((inp) => inp.addEventListener("input", () => recalcularTotal(tipo)));
  row.querySelector(".btn-remove").addEventListener("click", () => {
    if (cont.children.length > 1) {
      row.remove();
      recalcularTotal(tipo);
    }
  });

  cont.appendChild(row);
  syncPrecio();
}

function recalcularTotal(tipo) {
  let total = 0;
  document.querySelectorAll(`#${tipo}-items .item-row`).forEach((row) => {
    const c = Number(row.querySelector(".item-cant").value || 0);
    const p = Number(row.querySelector(".item-precio").value || 0);
    const iva = Number(row.querySelector(".item-iva").value || 0);
    total += c * p * (1 + iva);
  });
  document.getElementById(`${tipo}-total`).textContent = money(total);
}

function extraerDetalles(tipo) {
  const filas = document.querySelectorAll(`#${tipo}-items .item-row`);
  return Array.from(filas).map((row) => ({
    id_producto: Number(row.querySelector(".item-prod").value),
    cantidad: Number(row.querySelector(".item-cant").value),
    precioUnitario: Number(row.querySelector(".item-precio").value),
    porcentaje_iva: Number(row.querySelector(".item-iva").value),
  }));
}

async function cargarProductos() {
  const todos = document.getElementById("chk-todos-productos").checked ? "?todos=1" : "";
  const lista = await fetchJSON(`${API}/productos${todos}`);
  const tbody = document.getElementById("tbody-productos");
  tbody.innerHTML = lista
    .map((p) => {
      const stockBajo = Number(p.cantidad_stock) <= Number(p.nivel_minimo);
      return `
      <tr>
        <td>${p.id_producto}</td>
        <td>${p.nombre}</td>
        <td>${p.cantidad_stock} ${stockBajo ? '<span class="badge badge-warn">Bajo</span>' : ""}</td>
        <td>${p.nivel_minimo}</td>
        <td>${money(p.precioCompra)}</td>
        <td>${money(p.precioVenta)}</td>
        <td>${(Number(p.tarifa_iva) * 100).toFixed(0)}%</td>
        <td><span class="badge ${p.estado ? "badge-ok" : "badge-off"}">${p.estado ? "Activo" : "Inactivo"}</span></td>
        <td class="actions">
          <button class="btn btn-secondary btn-sm" onclick='editarProducto(${JSON.stringify(p)})'>Editar</button>
          ${
            p.estado
              ? `<button class="btn btn-danger btn-sm" onclick="cambiarEstadoProducto(${p.id_producto}, 0)">Inactivar</button>`
              : `<button class="btn btn-success btn-sm" onclick='reactivarProducto(${JSON.stringify(p)})'>Activar</button>`
          }
        </td>
      </tr>`;
    })
    .join("");
}

window.editarProducto = (p) => {
  document.getElementById("titulo-form-producto").textContent = `Editar Producto #${p.id_producto}`;
  document.getElementById("prod-id").value = p.id_producto;
  document.getElementById("prod-nombre").value = p.nombre;
  document.getElementById("prod-stock").value = p.cantidad_stock;
  document.getElementById("prod-stock").disabled = true;
  document.getElementById("prod-minimo").value = p.nivel_minimo;
  document.getElementById("prod-compra").value = p.precioCompra;
  document.getElementById("prod-compra").disabled = true;
  document.getElementById("prod-venta").value = p.precioVenta;
  document.getElementById("prod-iva").value = p.tarifa_iva;
  document.getElementById("btn-cancelar-prod").classList.remove("hidden");
};

function limpiarFormProducto() {
  document.getElementById("titulo-form-producto").textContent = "Nuevo Producto";
  document.getElementById("form-producto").reset();
  document.getElementById("prod-id").value = "";
  document.getElementById("prod-stock").disabled = false;
  document.getElementById("prod-compra").disabled = false;
  document.getElementById("prod-minimo").value = 5;
  document.getElementById("prod-iva").value = 0.19;
  document.getElementById("btn-cancelar-prod").classList.add("hidden");
}

window.cambiarEstadoProducto = async (id) => {
  try {
    const res = await fetchJSON(`${API}/productos/${id}`, { method: "DELETE" });
    mostrarAlerta(res.mensaje);
    await refrescarTodo();
  } catch (err) {
    mostrarAlerta(err.message, "err");
  }
};

window.reactivarProducto = async (p) => {
  try {
    const res = await fetchJSON(`${API}/productos/${p.id_producto}`, {
      method: "PUT",
      body: JSON.stringify({ ...p, estado: 1 }),
    });
    mostrarAlerta(res.mensaje);
    await refrescarTodo();
  } catch (err) {
    mostrarAlerta(err.message, "err");
  }
};

document.getElementById("btn-cancelar-prod").addEventListener("click", limpiarFormProducto);
document.getElementById("chk-todos-productos").addEventListener("change", cargarProductos);

document.getElementById("form-producto").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = document.getElementById("prod-id").value;
  const payload = {
    nombre: document.getElementById("prod-nombre").value.trim(),
    cantidad_stock: Number(document.getElementById("prod-stock").value),
    nivel_minimo: Number(document.getElementById("prod-minimo").value),
    precioCompra: Number(document.getElementById("prod-compra").value),
    precioVenta: Number(document.getElementById("prod-venta").value),
    tarifa_iva: Number(document.getElementById("prod-iva").value),
  };
  try {
    const res = id
      ? await fetchJSON(`${API}/productos/${id}`, { method: "PUT", body: JSON.stringify(payload) })
      : await fetchJSON(`${API}/productos`, { method: "POST", body: JSON.stringify(payload) });
    mostrarAlerta(res.mensaje);
    limpiarFormProducto();
    await refrescarTodo();
  } catch (err) {
    mostrarAlerta(err.message, "err");
  }
});

async function cargarTerceros() {
  const todos = document.getElementById("chk-todos-terceros").checked ? "?todos=1" : "";
  const lista = await fetchJSON(`${API}/terceros${todos}`);
  const tbody = document.getElementById("tbody-terceros");
  tbody.innerHTML = lista
    .map(
      (t) => `
      <tr>
        <td>${t.id_tercero}</td>
        <td>${t.nombre}</td>
        <td>${t.correo || "-"}</td>
        <td>${t.contacto}</td>
        <td><span class="badge ${t.estado ? "badge-ok" : "badge-off"}">${t.estado ? "Activo" : "Inactivo"}</span></td>
        <td class="actions">
          <button class="btn btn-secondary btn-sm" onclick='editarTercero(${JSON.stringify(t)})'>Editar</button>
          ${
            t.estado
              ? `<button class="btn btn-danger btn-sm" onclick="inactivarTercero(${t.id_tercero})">Inactivar</button>`
              : `<button class="btn btn-success btn-sm" onclick='reactivarTercero(${JSON.stringify(t)})'>Activar</button>`
          }
        </td>
      </tr>`
    )
    .join("");
}

window.editarTercero = (t) => {
  document.getElementById("titulo-form-tercero").textContent = `Editar Tercero #${t.id_tercero}`;
  document.getElementById("terc-id").value = t.id_tercero;
  document.getElementById("terc-nombre").value = t.nombre;
  document.getElementById("terc-correo").value = t.correo || "";
  document.getElementById("terc-contacto").value = t.contacto;
  document.getElementById("btn-cancelar-terc").classList.remove("hidden");
};

function limpiarFormTercero() {
  document.getElementById("titulo-form-tercero").textContent = "Nuevo Tercero";
  document.getElementById("form-tercero").reset();
  document.getElementById("terc-id").value = "";
  document.getElementById("btn-cancelar-terc").classList.add("hidden");
}

window.inactivarTercero = async (id) => {
  try {
    const res = await fetchJSON(`${API}/terceros/${id}`, { method: "DELETE" });
    mostrarAlerta(res.mensaje);
    await refrescarTodo();
  } catch (err) {
    mostrarAlerta(err.message, "err");
  }
};

window.reactivarTercero = async (t) => {
  try {
    const res = await fetchJSON(`${API}/terceros/${t.id_tercero}`, {
      method: "PUT",
      body: JSON.stringify({ ...t, estado: 1 }),
    });
    mostrarAlerta(res.mensaje);
    await refrescarTodo();
  } catch (err) {
    mostrarAlerta(err.message, "err");
  }
};

document.getElementById("btn-cancelar-terc").addEventListener("click", limpiarFormTercero);
document.getElementById("chk-todos-terceros").addEventListener("change", cargarTerceros);

document.getElementById("form-tercero").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = document.getElementById("terc-id").value;
  const payload = {
    nombre: document.getElementById("terc-nombre").value.trim(),
    correo: document.getElementById("terc-correo").value.trim() || null,
    contacto: document.getElementById("terc-contacto").value.trim(),
  };
  try {
    const res = id
      ? await fetchJSON(`${API}/terceros/${id}`, { method: "PUT", body: JSON.stringify(payload) })
      : await fetchJSON(`${API}/terceros`, { method: "POST", body: JSON.stringify(payload) });
    mostrarAlerta(res.mensaje);
    limpiarFormTercero();
    await refrescarTodo();
  } catch (err) {
    mostrarAlerta(err.message, "err");
  }
});

const ESTADOS = ["Pendiente", "Pagado", "Enviado", "Por Pagar", "Anulado"];

function renderSelectEstado(actual, onChangeFn, deshabilitarAnulado = false) {
  const dis = deshabilitarAnulado && actual === "Anulado" ? "disabled" : "";
  const opts = ESTADOS.map((e) => `<option value="${e}" ${e === actual ? "selected" : ""}>${e}</option>`).join("");
  return `<select ${dis} onchange="${onChangeFn}">${opts}</select>`;
}

async function cargarPedidos() {
  const lista = await fetchJSON(`${API}/pedidos`);
  document.getElementById("kpi-pedidos").textContent = lista.length;
  document.getElementById("tbody-pedidos").innerHTML = lista
    .map(
      (p) => `
      <tr>
        <td>#${p.id_pedido}</td>
        <td>${new Date(p.fecha_pedido).toLocaleString("es-CO")}</td>
        <td>${p.nombre_tercero}</td>
        <td>${p.nombre_usuario}</td>
        <td>${money(p.total_pedido)}</td>
        <td>${renderSelectEstado(p.estado_pedido, `cambiarEstadoPedido(${p.id_pedido}, this.value)`, true)}</td>
        <td><button class="btn btn-secondary btn-sm" onclick="verDetalle('pedido', ${p.id_pedido})">Ver Detalle</button></td>
      </tr>`
    )
    .join("");
}

window.cambiarEstadoPedido = async (id, estado) => {
  try {
    const res = await fetchJSON(`${API}/pedidos/${id}/estado`, {
      method: "PUT",
      body: JSON.stringify({ estado_pedido: estado }),
    });
    mostrarAlerta(res.mensaje);
    await refrescarTodo();
  } catch (err) {
    mostrarAlerta(err.message, "err");
    await cargarPedidos();
  }
};

document.getElementById("btn-add-pedido-item").addEventListener("click", () => crearFilaItem("pedido"));

const ESTADOS_CREACION = ["Pendiente", "Pagado", "Enviado", "Por Pagar"];

document.getElementById("form-pedido").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const estado = document.getElementById("pedido-estado").value;
    if (!ESTADOS_CREACION.includes(estado)) {
      throw new Error("Estado de pedido inválido.");
    }
    const payload = {
      tercero_id_tercero: Number(document.getElementById("pedido-tercero").value),
      usuarios_id_usuario: Number(document.getElementById("pedido-usuario").value),
      estado_pedido: estado,
      detalles: extraerDetalles("pedido"),
    };
    const res = await fetchJSON(`${API}/pedidos`, { method: "POST", body: JSON.stringify(payload) });
    mostrarAlerta(`${res.mensaje} (ID #${res.id_pedido})`);
    document.getElementById("pedido-items").innerHTML = "";
    await refrescarTodo();
  } catch (err) {
    mostrarAlerta(err.message, "err");
  }
});

async function cargarVentas() {
  const lista = await fetchJSON(`${API}/ventas`);
  document.getElementById("kpi-ventas").textContent = lista.length;
  document.getElementById("tbody-ventas").innerHTML = lista
    .map(
      (v) => `
      <tr>
        <td>#${v.id_venta}</td>
        <td>${new Date(v.fecha_venta).toLocaleString("es-CO")}</td>
        <td>${v.nombre_tercero}</td>
        <td>${v.nombre_usuario}</td>
        <td>${money(v.total_venta)}</td>
        <td>${renderSelectEstado(v.estado_venta, `cambiarEstadoVenta(${v.id_venta}, this.value)`, true)}</td>
        <td class="actions">
          <button class="btn btn-secondary btn-sm" onclick="verDetalle('venta', ${v.id_venta})">Ver Detalle</button>
          ${v.estado_venta !== "Anulado" ? `<button class="btn btn-danger btn-sm" onclick="cambiarEstadoVenta(${v.id_venta}, 'Anulado')">Anular</button>` : ""}
        </td>
      </tr>`
    )
    .join("");
}

window.cambiarEstadoVenta = async (id, estado) => {
  try {
    const res =
      estado === "Anulado"
        ? await fetchJSON(`${API}/ventas/${id}/anular`, { method: "PUT" })
        : await fetchJSON(`${API}/ventas/${id}/estado`, {
            method: "PUT",
            body: JSON.stringify({ estado_venta: estado }),
          });
    mostrarAlerta(res.mensaje);
    await refrescarTodo();
  } catch (err) {
    mostrarAlerta(err.message, "err");
    await cargarVentas();
  }
};

document.getElementById("btn-add-venta-item").addEventListener("click", () => crearFilaItem("venta"));

document.getElementById("form-venta").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const estado = document.getElementById("venta-estado").value;
    if (!ESTADOS_CREACION.includes(estado)) {
      throw new Error("Estado de venta inválido.");
    }
    const payload = {
      tercero_id_tercero: Number(document.getElementById("venta-tercero").value),
      usuarios_id_usuario: Number(document.getElementById("venta-usuario").value),
      estado_venta: estado,
      detalles: extraerDetalles("venta"),
    };
    const res = await fetchJSON(`${API}/ventas`, { method: "POST", body: JSON.stringify(payload) });
    mostrarAlerta(`${res.mensaje} (ID #${res.id_venta})`);
    document.getElementById("venta-items").innerHTML = "";
    await refrescarTodo();
  } catch (err) {
    mostrarAlerta(err.message, "err");
  }
});

window.verDetalle = async (tipo, id) => {
  try {
    const endpoint = tipo === "venta" ? "ventas" : "pedidos";
    const data = await fetchJSON(`${API}/${endpoint}/${id}`);
    document.getElementById("modal-titulo").textContent =
      tipo === "venta" ? `Detalle de Venta #${data.id_venta}` : `Detalle de Pedido #${data.id_pedido}`;
    document.getElementById("modal-info").innerHTML = `
      <span><strong>Tercero:</strong> ${data.nombre_tercero}</span>
      <span><strong>Usuario:</strong> ${data.nombre_usuario}</span>
      <span><strong>Estado:</strong> ${data.estado_venta || data.estado_pedido}</span>
      <span><strong>Total:</strong> ${money(data.total_venta ?? data.total_pedido)}</span>
    `;
    document.getElementById("modal-tbody").innerHTML = data.detalles
      .map((d) => {
        const totalLinea = d.total_venta ?? d.total_producto ?? Number(d.subtotal) * (1 + Number(d.porcentaje_iva));
        return `
        <tr>
          <td>${d.nombre_producto}</td>
          <td>${d.cantidad}</td>
          <td>${money(d.precioUnitario)}</td>
          <td>${money(d.subtotal)}</td>
          <td>${(Number(d.porcentaje_iva) * 100).toFixed(0)}%</td>
          <td>${money(totalLinea)}</td>
        </tr>`;
      })
      .join("");
    document.getElementById("modal-detalle").classList.remove("hidden");
  } catch (err) {
    mostrarAlerta(err.message, "err");
  }
};

document.getElementById("modal-cerrar").addEventListener("click", () => {
  document.getElementById("modal-detalle").classList.add("hidden");
});

async function refrescarTodo() {
  await cargarCatalogos();
  await Promise.all([cargarProductos(), cargarTerceros(), cargarPedidos(), cargarVentas()]);
  if (document.getElementById("venta-items").children.length === 0 && productosCache.length > 0) {
    crearFilaItem("venta");
  }
  if (document.getElementById("pedido-items").children.length === 0 && productosCache.length > 0) {
    crearFilaItem("pedido");
  }
}

refrescarTodo().catch((err) => mostrarAlerta(err.message, "err"));
