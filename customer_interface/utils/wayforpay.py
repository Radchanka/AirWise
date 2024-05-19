import base64
import time
import requests
import hashlib
import hmac

SECRET_KEY = 'flk3409refn54t54t*FNJRET'
domain_name = '34.70.195.173'
merchantAccount = 'test_merch_n1'
WAYFORPAY_API = "https://api.wayforpay.com/api"


def generate_hmac(data, secret_key):
    message = ';'.join(data).encode('utf-8')
    secret_key = secret_key.encode('utf-8')
    return hmac.new(secret_key, message, hashlib.md5).hexdigest()


def generate_response_signature(orderReference, status, time, secret_key):
    data = f"{orderReference};{status};{time}".encode('utf-8')
    signature = hmac.new(secret_key.encode('utf-8'), data, hashlib.md5).hexdigest()
    return signature


def encode_order_reference(order):
    order_id = int(order) + 10000111
    return hex(order_id)[2:]


def decode_order_reference(order_id):
    return int(order_id, 16) - 10000111


def create_request_params(price, email, ticket_count, order_id):
    orderReference = encode_order_reference(order_id)
    orderDate = int(time.time())

    params = {
        "transactionType": "CREATE_INVOICE",
        "merchantAccount": merchantAccount,
        "merchantDomainName": domain_name,
        "apiVersion": 1,
        "language": "en",
        "serviceUrl": "http://34.70.195.173/api/v1/wayforpay_callback/",
        "orderReference": orderReference,
        "orderDate": orderDate,
        "amount": price,
        "currency": "UAH",
        "orderTimeout": 86400,
        "productName": ["Air Ticket"],
        "productPrice": [21.1],
        "productCount": [ticket_count],
        "paymentSystems": "card;privat24",
        "clientEmail": email,
        "order_id": order_id,
    }

    # Формирование подписи HMAC_MD5
    data_to_sign = [
        params["merchantAccount"],
        params["merchantDomainName"],
        params["orderReference"],
        str(params["orderDate"]),
        str(params["amount"]),
        params["currency"]
    ]
    for product in params["productName"]:
        data_to_sign.append(product)
    for count in params["productCount"]:
        data_to_sign.append(str(count))
    for price in params["productPrice"]:
        data_to_sign.append(str(price))

    params["merchantSignature"] = generate_hmac(data_to_sign, SECRET_KEY)

    return params


def send_request(params):
    response = requests.post(WAYFORPAY_API, json=params)
    return response


def handle_response(response):
    if response.status_code == 200:
        response_data = response.json()
        # Обработка данных ответа согласно вашим потребностям
        return response_data
    else:
        return {"error": f"Ошибка при выполнении запроса: {response.status_code}"}
