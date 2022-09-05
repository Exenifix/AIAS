FROM python:3.10-bullseye

RUN pip install --no-cache-dir 'poetry>=1.2.0,<1.3'
COPY pyproject.toml poetry.lock /app/
WORKDIR /app
RUN poetry install --no-dev

COPY . .

ENTRYPOINT ["poetry", "run", "python"]
CMD ["main.py"]
