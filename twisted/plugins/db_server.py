from twisted.application.service import ServiceMaker

db_server = ServiceMaker(
    'dp_server', 'dp.server.tap', 'Run a dp server service', 'dpserver')