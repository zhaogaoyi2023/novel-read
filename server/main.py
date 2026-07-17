"""
Novel Read Server - Main Entry Point

This module initializes and starts the Novel Read server application.
"""

import uvicorn
from loguru import logger
from pathlib import Path

from server.core.config import settings


def main():
    """Main entry point for the server."""
    logger.info("Starting Novel Read Server...")
    logger.info(f"Configuration loaded from: {settings.config_file}")
    logger.info(f"Database: {settings.database_url}")
    
    # Ensure data directories exist
    Path("./data").mkdir(exist_ok=True)
    Path("./logs").mkdir(exist_ok=True)
    Path("./keys").mkdir(exist_ok=True)
    
    # Start the server
    uvicorn.run(
        "server.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug"
    )


if __name__ == "__main__":
    main()
