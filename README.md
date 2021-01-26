# APRS 2 SMS Gateway

Este script revisa las tramas de la red **APRS** buscando una cadena en particular, si la encuentra procesa el contenido y envía un mensaje de SMS.


# Instalación

Solo se debe copiar el script a una maquina tipo *nix, se necesita un interprete de Python, y las siguientes librerias

json
re
requests
MySQLdb
unidecode


## Problemas

La conexión a la red celular se hace por medio de una API, esta API en ocasiones presenta retrasos, de momento no hay un mecanismo para permitir respuesta a los mensajes por parte de la persona que lo recibe, la comunicación es de una vía.


## Licencia
Este código usa la licencia GNU General Public License V3, se ofrece tal y como esta, el uso de este código es bajo su propio riesgo.
