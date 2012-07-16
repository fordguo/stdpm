from twisted.application.service import ServiceMaker

db_server = ServiceMaker(
    'dp_client', 'dp.client.tap', 'Run a dp client service', 'dpclient')