import os
import logging
import time

import mongoengine
from gameBot.models import Word, FofState
from logging import INFO

mongoengine.connect(
    db=os.environ.get('MONGODB_DB', 'wordsquad'),
    host=os.environ.get('MONGODB_HOST', 'localhost'),
    username=os.environ.get('MONGODB_USERNAME', 'root'),
    password=os.environ.get('MONGODB_PASSWORD', 'pass'),
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

batch_size = int(os.environ.get('BATCH_SIZE', 100))
batch_interval = int(os.environ.get('BATCH_INTERVAL', 10))

def main() -> None:
    for i in range(batch_size):
        word = Word.pick_one(5)
        logger.info(f"Processing thesaurus for word: {word.word}:{word.fof}...")
        if word.fof == FofState.ready:
            logger.info(f"Word {word.word} has been processed, skipping...")
            continue
        if word.fof == FofState.failed:
            logger.info(f"Word {word.word} has failed, skipping...")
            continue
        word.prepare_thesaurus()
        time.sleep(batch_interval)

if __name__ == '__main__':
    main()
