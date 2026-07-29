ruta = 'templates/base.html'
with open(ruta, 'r', encoding='utf-8') as f:
    b = f.read()

if 'beta-banner' in b:
    print("El banner beta ya existe. Sin cambios.")
    raise SystemExit

# Insertar el banner justo despues de abrir <body>
banner = '''<body>
<div class="beta-banner" style="background:#0E6BB8; color:#fff; text-align:center; font-size:12px; padding:5px 12px;">
  🚧 RETACHE está en versión beta. Estamos mejorando la plataforma cada día. La Carta Porte se genera con tus datos; el timbrado oficial ante el SAT se realiza aparte con un PAC autorizado.
</div>'''

if '<body>' in b:
    b = b.replace('<body>', banner, 1)
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(b)
    print("Banner beta agregado al inicio de todas las paginas")
else:
    print("NO se encontro <body>. Revisar manual.")