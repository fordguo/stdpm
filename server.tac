
serverPort = 56024
ftpPort = 56021
httpPort = 56080

# Create a MultiService, and hook up a TCPServer and a FTPServer and a HTTPServer to it as
# children.
serverService = service.MultiService()
internet.TCPServer(serverPort, CoreServerFactory()).setServiceParent(serverService)
internet.TCPServer(ftpPort,initFtpFactory()).setServiceParent(serverService)
internet.TCPServer(httpPort,server.Site(root)).setServiceParent(serverService)
# Create an application as normal
application = service.Application("SPDM Server")

# Connect our MultiService to the application, just like a normal service.
serverService.setServiceParent(application)