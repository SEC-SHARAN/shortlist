FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
RUN useradd -r -u 10001 ats
COPY requirements.txt requirements-ml.txt ./
ARG WITH_ML=0
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$WITH_ML" = "1" ]; then pip install --no-cache-dir -r requirements-ml.txt && python -m spacy download en_core_web_sm \
    && python -c "from sentence_transformers import SentenceTransformer as S; S('sentence-transformers/all-MiniLM-L6-v2')"; fi
COPY app ./app
RUN mkdir -p /data/resumes && chown -R ats /data /srv
USER ats
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
