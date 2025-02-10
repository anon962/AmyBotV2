import asyncio

from uvicorn import Config, Server

from classes.core.server.server import (
    create_name_dictionary_task,
    create_range_update_task,
)

if __name__ == "__main__":

    loop = asyncio.new_event_loop()

    loop.create_task(create_range_update_task())
    loop.create_task(create_name_dictionary_task())

    server = Server(
        config=Config(
            app="classes.core.server.server:server",
            loop=loop,  # type: ignore
            host="0.0.0.0",
            port=4545,
        )
    )

    loop.run_until_complete(server.serve())
