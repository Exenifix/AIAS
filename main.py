import sys

from utils.bot import Bot
from utils.constants import WELCOME_MESSAGE

print(WELCOME_MESSAGE, file=sys.stderr)

Bot().run()
