from alchemysession import AlchemySessionContainer

from . import BASE

container = AlchemySessionContainer(engine=BASE.metadata.bind, table_base=BASE, manage_tables=False,
                                    table_prefix="telethonian_")
