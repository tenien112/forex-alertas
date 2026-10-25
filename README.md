# Vigilante FOREX by Lorenzo

Cada 30 minutos (lunes a viernes, hora de Madrid) comprueba 19 mercados (incluido Bitcoin) en M30, H1 y H2 con los 4 indicadores y avisa al móvil por ntfy (tema forex-lorenzito-7k3q9) cuando un mercado se alinea ALCISTA/BAJISTA o deja de estarlo.

Prueba manual: pestaña Actions → Vigilante FOREX → Run workflow → marcar 'prueba'.

# Vigilante ATALAYA by Lorenzo

Cada día a las 8:43 (Madrid) calcula con el mismo algoritmo que la app ATALAYA la probabilidad de patera y taxi para hoy, mañana y pasado, y la manda al móvil por ntfy. Si alguna supera el 70 %, el aviso sale como POSIBLE LLEGADA.

# Vigilante ORO y PLATA by Lorenzo

Cada 30 minutos (domingo noche a viernes noche) replica el cBot CLAUDE-VIGILANTE-MULTI-TF-BOT con la configuración del oro (M30, H1, H2, H4; salida con M30; solo alineación nueva) sobre ORO (GC=F) y PLATA (SI=F) y avisa por ntfy (tema forex-lorenzito-7k3q9) de cada COMPRA, VENTA y CIERRE para operarlas a mano en XTB. No depende de cTrader. Guarda en estado_oro.json la hora del último aviso para no repetir.

Resumen diario de lunes a viernes sobre las 9 (Madrid). Prueba manual: pestaña Actions → Vigilante ORO y PLATA → Run workflow → marcar 'prueba'.
