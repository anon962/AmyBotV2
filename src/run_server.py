if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "classes.core.server.server:server", host="0.0.0.0", port=4545, reload=True
    )
