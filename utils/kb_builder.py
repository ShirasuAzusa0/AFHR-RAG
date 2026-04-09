import logging
from api import create_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting KB build process...")

    app = create_app()

    with app.app_context():
        app.rag_service.build_and_store_all_articles()

    logger.info("KB build finished.")