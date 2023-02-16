from dotenv import load_dotenv
from exenenv import EnvironmentProfile


class MainEnvironment(EnvironmentProfile):
    TOKEN: str
    TOPGG_TOKEN: str
    TEST_VERSION: bool = False


class DatabaseEnvironment(EnvironmentProfile):
    DATABASE: str
    USER: str
    HOST: str = "127.0.0.1"
    PASSWORD: str | None = None


load_dotenv()

main = MainEnvironment()
main.load()

db = DatabaseEnvironment()
db.load()
