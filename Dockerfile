FROM python:3.10-bullseye

ENV VIRTUAL_ENV=/app/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY . /app
RUN pip install -r requirements.txt

ENTRYPOINT ["python"]
RUN ["ai/train.py"]
CMD ["main.py"]
