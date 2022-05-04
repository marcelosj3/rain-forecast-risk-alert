import asyncio
from http import HTTPStatus

from flask import jsonify, request
from flask_jwt_extended import create_access_token, decode_token, jwt_required
from sqlalchemy.orm import Query, Session

from app.configs.database import db
from app.exceptions.city_exc import (
    CityNotFoundError,
    CityOutOfRangeError,
    ZipCodeNotFoundError,
)
from app.exceptions.generic_exc import InvalidKeysError
from app.exceptions.user_exc import UserNotFound
from app.models.address_model import AddressModel
from app.models.user_model import UserModel
from app.services.generic_services import get_user_from_token
from app.services.user_services import validate_keys_and_values
from app.utils.zip_code_validate import validate_zip_code


def signup():
    session: Session = db.session
    data = request.get_json()

    cep = data.pop("cep")

    try:

        city_query = asyncio.run(validate_zip_code(cep))
        cep_query = session.query(AddressModel).filter_by(cep=cep).first()

        new_user = UserModel(**data)

        if cep_query:
            new_user.address = cep_query
        else:
            new_cep = AddressModel(cep=cep)
            new_cep.city = city_query
            new_user.address = new_cep

        session.commit()
    except ZipCodeNotFoundError as e:
        return e.message, e.status_code
    except CityNotFoundError as e:
        return e.message, e.status_code
    except CityOutOfRangeError as e:
        return e.message, e.status_code

    return (
        jsonify(
            {
                "name": new_user.name,
                "email": new_user.email,
                "phone": new_user.phone,
                "address": new_user.address.cep,
                "city": city_query.name,
                "state": city_query.state.name,
            }
        ),
        HTTPStatus.CREATED,
    )


def signin():
    data = request.get_json()

    user: UserModel = UserModel.query.filter_by(email=data["email"]).first()

    if not user:
        return {"message": "User not found"}, HTTPStatus.NOT_FOUND

    if user.verify_password(data["password"]):
        token = create_access_token(user.id)
        return {"token": token}, HTTPStatus.OK

    else:
        return {"message": "Unauthorized"}, HTTPStatus.UNAUTHORIZED


@jwt_required()
def retrieve():

    session: Session = db.session

    base_query: Query = session.query(UserModel)

    users = base_query.all()

    return (
        jsonify(
            [
                {
                    "name": user.name,
                    "email": user.email,
                    "phone": user.phone,
                    "address": user.address.cep,
                    "city": user.address.city.name,
                    "state": user.address.city.state.name,
                }
                for user in users
            ]
        ),
        HTTPStatus.OK,
    )


@jwt_required()
def delete():
    session: Session = db.session

    try:
        user = get_user_from_token()
        if not user:
            raise UserNotFound
    except UserNotFound as e:
        return e.message, e.status_code

    session.delete(user)
    session.commit()

    return "", HTTPStatus.NO_CONTENT


@jwt_required()
def patch():
    session: Session = db.session
    allowed_keys = ["email", "phone", "name", "password"]
    try:
        data = request.get_json()
        user = get_user_from_token()
        validate_keys_and_values(data, user, allowed_keys)

    except InvalidKeysError as e:
        return e.message, e.status_code
    except UserNotFound as e:
        return e.message, e.status_code

    session.commit()

    return "", HTTPStatus.NO_CONTENT
