import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os

# Установка флага тестирования
os.environ["TESTING"] = "1"

# Импорт компонентов приложения
from main import api_application, obtain_database_session, Base, PersonRecord, engine

# Создание тестовой сессии
TestSessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Фикстура для базы данных
@pytest.fixture
def test_database_session():
    database = TestSessionFactory()
    try:
        yield database
    finally:
        database.close()


# Фикстура тестового клиента
@pytest.fixture
def test_client(test_database_session):
    # Заменяем зависимость базы данных
    api_application.dependency_overrides[obtain_database_session] = lambda: test_database_session

    # Инициализация схемы данных
    Base.metadata.create_all(bind=engine)
    yield TestClient(api_application)
    # Очистка после тестов
    Base.metadata.drop_all(bind=engine)


# Данные для тестирования
SAMPLE_RECORD = {
    "name": "Johnathan Davis",
    "age": 30,
    "address": "123 Maple Street",
    "work": "Software Engineer"
}

UPDATED_RECORD = {
    "name": "Janet Smithson",
    "age": 25,
    "address": "456 Oak Boulevard",
    "work": "Data Scientist"
}


class TestPeopleRecordsAPI:
    def test_successful_record_creation(self, test_client):
        """Проверка корректного создания записи"""
        result = test_client.post("/persons", json=SAMPLE_RECORD)

        assert result.status_code == 201
        assert result.headers["Location"] == "/persons/1"

    def test_successful_record_retrieval(self, test_client):
        """Проверка получения данных записи"""
        # Создание тестовой записи
        test_client.post("/persons", json=SAMPLE_RECORD)

        # Получение созданной записи
        result = test_client.get("/persons/1")

        assert result.status_code == 200
        response_data = result.json()
        assert response_data["id"] == 1
        assert response_data["name"] == "Johnathan Davis"
        assert response_data["age"] == 30

    def test_missing_record_retrieval(self, test_client):
        """Проверка обработки запроса отсутствующей записи"""
        result = test_client.get("/persons/999")

        assert result.status_code == 404
        assert result.json()["detail"] == "Record not found"

    def test_retrieve_all_records(self, test_client):
        """Проверка получения полного списка записей"""
        # Создание нескольких тестовых записей
        test_client.post("/persons", json=SAMPLE_RECORD)
        test_client.post("/persons", json=UPDATED_RECORD)

        result = test_client.get("/persons")

        assert result.status_code == 200
        response_data = result.json()
        assert len(response_data) == 2
        assert response_data[0]["name"] == "Johnathan Davis"
        assert response_data[1]["name"] == "Janet Smithson"

    def test_successful_record_modification(self, test_client):
        """Проверка обновления данных записи"""
        # Создание исходной записи
        test_client.post("/persons", json=SAMPLE_RECORD)

        # Модификация данных
        result = test_client.patch("/persons/1", json=UPDATED_RECORD)

        assert result.status_code == 200
        response_data = result.json()
        assert response_data["id"] == 1
        assert response_data["name"] == "Janet Smithson"
        assert response_data["age"] == 25

    def test_modify_missing_record(self, test_client):
        """Проверка обновления отсутствующей записи"""
        result = test_client.patch("/persons/999", json=UPDATED_RECORD)

        assert result.status_code == 404
        assert result.json()["detail"] == "Record not found"

    def test_successful_record_removal(self, test_client):
        """Проверка удаления записи"""
        # Создание записи для удаления
        test_client.post("/persons", json=SAMPLE_RECORD)

        # Удаление записи
        result = test_client.delete("/persons/1")

        assert result.status_code == 204

        # Проверка фактического удаления
        verification_result = test_client.get("/persons/1")
        assert verification_result.status_code == 404

    def test_remove_missing_record(self, test_client):
        """Проверка удаления отсутствующей записи"""
        result = test_client.delete("/persons/999")

        assert result.status_code == 404
        assert result.json()["detail"] == "Record not found"

    def test_complete_record_lifecycle(self, test_client):
        """Комплексная проверка полного цикла работы с записью"""
        # Создание новой записи
        creation_result = test_client.post("/persons", json=SAMPLE_RECORD)
        assert creation_result.status_code == 201

        # Извлечение идентификатора из заголовка
        location_header = creation_result.headers["Location"]
        identifier = location_header.split("/")[-1]

        # Получение созданной записи по ссылке
        retrieval_result = test_client.get(location_header)
        assert retrieval_result.status_code == 200

        response_data = retrieval_result.json()
        assert response_data["id"] == int(identifier)
        assert response_data["name"] == "Johnathan Davis"
        assert response_data["age"] == 30


# Запуск тестовой последовательности
if __name__ == "__main__":
    pytest.main([__file__, "-v"])