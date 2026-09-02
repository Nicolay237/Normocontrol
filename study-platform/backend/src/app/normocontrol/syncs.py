from app.normocontrol.schemas import NormocontrolRunOutput
from app.ws.api import ws_api

#: Область — конкретная проверка, а не материал: на странице материала сидят и
#: другие студенты, и рассылать им чужие отчёты незачем.
ws_api.register_sync("normocontrol.run.changed", output_type=NormocontrolRunOutput)
