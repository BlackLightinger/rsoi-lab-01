from fastapi import FastAPI, HTTPException, Depends, status, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel as PydanticBaseModel, ConfigDict
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import StaticPool
import os


# Database configuration handler
def initialize_database():
    if not os.getenv("TESTING"):
        database_user = os.getenv("POSTGRES_USER", "postgres")
        database_password = os.getenv("POSTGRES_PASSWORD", "postgres")
        database_name = os.getenv("POSTGRES_DB", "postgres")
        database_host = os.getenv("DB_HOST", "postgres")
        database_port = os.getenv("DB_PORT", "5432")

        connection_string = f"postgresql://{database_user}:{database_password}@{database_host}:{database_port}/{database_name}"

        database_engine = create_engine(connection_string)
        DatabaseSession = sessionmaker(autocommit=False, autoflush=False, bind=database_engine)
        ModelBase = declarative_base()
        return database_engine, DatabaseSession, ModelBase
    else:
        ModelBase = declarative_base()

        test_database_url = "sqlite:///:memory:"

        database_engine = create_engine(
            test_database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        return database_engine, sessionmaker(bind=database_engine), ModelBase


engine, DatabaseSessionLocal, Base = initialize_database()


# Data entity definition
class PersonRecord(Base):
    __tablename__ = "people_records"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    address = Column(String, nullable=False)
    work = Column(String, nullable=False)


# Initialize database schema
Base.metadata.create_all(bind=engine)


# Data validation schemas
class PersonInputData(PydanticBaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    age: int
    address: str
    work: str


class PersonCreationData(PersonInputData):
    pass


class PersonOutputData(PersonInputData):
    id: int


class ErrorMessageData(PydanticBaseModel):
    error_text: str


def create_error_response(error_message, http_code):
    return JSONResponse(
        content=ErrorMessageData(error_text=error_message).model_dump(),
        status_code=http_code
    )


# Application initialization
api_application = FastAPI(title="People Records API", root_path="/api/v1")


# Database session management
def obtain_database_session():
    database_session = DatabaseSessionLocal()
    try:
        yield database_session
    finally:
        database_session.close()


def fetch_person_record(identifier, database_session):
    person_data = database_session.query(PersonRecord).filter(
        PersonRecord.id == identifier
    ).first()

    if person_data is None:
        raise HTTPException(status_code=404, detail="Record not found")

    return person_data


@api_application.get("/persons/{identifier}", response_model=PersonOutputData)
def retrieve_person_record(identifier: int, database: Session = Depends(obtain_database_session)):
    return fetch_person_record(identifier, database)


@api_application.get("/persons", response_model=list[PersonOutputData])
def retrieve_all_persons(database: Session = Depends(obtain_database_session)):
    return database.query(PersonRecord).all()


@api_application.post("/persons", status_code=status.HTTP_201_CREATED)
def add_person_record(
        person_input: PersonCreationData,
        http_response: Response,
        database: Session = Depends(obtain_database_session)
):
    new_person = PersonRecord(**person_input.model_dump())
    database.add(new_person)
    database.commit()
    database.refresh(new_person)

    http_response.headers["Location"] = f"/persons/{new_person.id}"
    return None


@api_application.patch("/persons/{identifier}", response_model=PersonOutputData)
def modify_person_record(
        identifier: int,
        update_data: dict,
        database: Session = Depends(obtain_database_session)
):
    person_record = fetch_person_record(identifier, database)

    for attribute_name, attribute_value in update_data.items():
        if not hasattr(person_record, attribute_name):
            return create_error_response("Invalid field provided", 400)
        setattr(person_record, attribute_name, attribute_value)

    database.commit()
    database.refresh(person_record)
    return person_record


@api_application.delete("/persons/{identifier}", status_code=204)
def remove_person_record(
        identifier: int,
        database: Session = Depends(obtain_database_session)
):
    person_data = fetch_person_record(identifier, database)

    database.delete(person_data)
    database.commit()