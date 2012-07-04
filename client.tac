from twisted.application import internet, service
from dp_client import CoreClientFactory

serverPort = 56024
ftpPort = 56021

# Create a MultiService, and hook up a TCPClient and a FTPClient to it as
# children.
serverService = service.MultiService()
internet.TCPClient('localhost',serverPort, CoreClientFactory()).setServiceParent(serverService)
# Create an application as normal
application = service.Application("SPDM Client")

# Connect our MultiService to the application, just like a normal service.
serverService.setServiceParent(application)