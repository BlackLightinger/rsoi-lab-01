import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os

# Установка флага тестирования
os.environ["TESTING"] = "1"

# Импорт компонентов приложения
from main import api_application, obtain_database_session, BaseModel, PersonRecord, engine

# Создание тестовой сессии
TestSessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Замена зависимости базы данных
def test_database_provider():
    try:
        database = TestSessionFactory()
        yield database
    finally:
        database.close()


api_application.dependency_overrides[obtain_database_session] = test_database_provider


# Фикстура тестового клиента
@pytest.fixture
def test_client():
    # Инициализация схемы данных
    BaseModel.metadata.create_all(bind=engine)
    yield TestClient(api_application)
    # Очистка после тестов
    BaseModel.metadata.drop_all(bind=engine)


# Данные для тестирования
SAMPLE_RECORD = {
    "full_name": "Johnathan Davis",
    "years_old": 30,
    "residence": "123 Maple Street",
    "profession": "Software Engineer"
}

UPDATED_RECORD = {
    "full_name": "Janet Smithson",
    "years_old": 25,
    "residence": "456 Oak Boulevard",
    "profession": "Data Scientist"
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
        assert response_data["record_id"] == 1
        assert response_data["full_name"] == "Johnathan Davis"
        assert response_data["years_old"] == 30

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
        assert response_data[0]["full_name"] == "Johnathan Davis"
        assert response_data[1]["full_name"] == "Janet Smithson"

    def test_successful_record_modification(self, test_client):
        """Проверка обновления данных записи"""
        # Создание исходной записи
        test_client.post("/persons", json=SAMPLE_RECORD)

        # Модификация данных
        result = test_client.patch("/persons/1", json=UPDATED_RECORD)

        assert result.status_code == 200
        response_data = result.json()
        assert response_data["record_id"] == 1
        assert response_data["full_name"] == "Janet Smithson"
        assert response_data["years_old"] == 25

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
        record_identifier = location_header.split("/")[-1]

        # Получение созданной записи по ссылке
        retrieval_result = test_client.get(location_header)
        assert retrieval_result.status_code == 200

        response_data = retrieval_result.json()
        assert response_data["record_id"] == int(record_identifier)
        assert response_data["full_name"] == "Johnathan Davis"
        assert response_data["years_old"] == 30


# Запуск тестовой последовательности
if __name__ == "__main__":
    pytest.main([__file__, "-v"])