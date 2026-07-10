content = """{% extends "admin/base_admin.html" %}
{% block title %}Cargas{% endblock %}
{% block content %}
<div class="page-title">Todas las cargas ({{ cargas|length }})</div>
<div class="card">
  <table>
    <thead>
      <tr>
        <th>Mercancia</th>
        <th>Ruta</th>
        <th>Empresa</th>
        <th>Precio</th>
        <th>Estado</th>
        <th>Fecha</th>
        <th>Accion</th>
      </tr>
    </thead>
    <tbody>
      {% for c in cargas %}
      <tr>
        <td>{{ c.tipo_mercancia }}</td>
        <td>{{ c.origen_ciudad }} - {{ c.destino_ciudad }}</td>
        <td>{{ c.empresa.razon_social if c.empresa else '-' }}</td>
        <td>${{ "{:,.0f}".format(c.precio_ofrecido_mxn) }}</td>
        <td>{{ c.estado }}</td>
        <td>{{ c.fecha_publicacion.strftime('%d %b %Y') }}</td>
        <td>
          <form action="/admin/cargas/{{ c.id }}/eliminar" method="POST" onsubmit="return confirm('Eliminar esta carga?')">
            <button type="submit" class="btn btn-rojo">Eliminar</button>
          </form>
        </td>
      </tr>
      {% else %}
      <tr>
        <td colspan="7" style="text-align:center; padding:24px; color:#8B8B8B;">
          No hay cargas registradas aun.
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}"""

with open('templates/admin/cargas.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Archivo guardado correctamente")