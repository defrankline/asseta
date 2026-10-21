import Foundation

/// `URLProtocol` stub that routes requests of a dedicated `URLSession` to an in-process handler, so
/// the real `URLSessionTransport` → `URLSession` stack is exercised. Each session gets its own
/// handler (looked up by a private header), which keeps parallel tests isolated.
public final class MockURLProtocol: URLProtocol, @unchecked Sendable {
    /// Returns `(status, body)` or throws (e.g. `URLError(.notConnectedToInternet)`) to simulate
    /// a network failure. The request passed in has its body materialized in `httpBody`.
    public typealias Handler = @Sendable (URLRequest) throws -> (Int, Data)

    private static let headerName = "X-Mock-Route"
    private static let lock = NSLock()
    nonisolated(unsafe) private static var handlers: [String: Handler] = [:]

    /// An ephemeral session whose requests are served by `handler`.
    public static func session(handler: @escaping Handler) -> URLSession {
        let route = UUID().uuidString
        lock.withLock { handlers[route] = handler }
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [MockURLProtocol.self]
        configuration.httpAdditionalHeaders = [headerName: route]
        configuration.urlCache = nil
        return URLSession(configuration: configuration)
    }

    public override class func canInit(with request: URLRequest) -> Bool { true }
    public override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    public override func startLoading() {
        var materialized = request
        if materialized.httpBody == nil, let stream = request.httpBodyStream {
            materialized.httpBody = Self.read(stream)
        }
        let route = request.value(forHTTPHeaderField: Self.headerName) ?? ""
        guard let handler = Self.lock.withLock({ Self.handlers[route] }) else {
            client?.urlProtocol(self, didFailWithError: URLError(.unsupportedURL))
            return
        }
        do {
            let (status, data) = try handler(materialized)
            let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: "HTTP/1.1",
                                           headerFields: ["Content-Type": "application/json"])!
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    public override func stopLoading() {}

    private static func read(_ stream: InputStream) -> Data {
        stream.open()
        defer { stream.close() }
        var data = Data()
        var buffer = [UInt8](repeating: 0, count: 64 * 1024)
        while stream.hasBytesAvailable {
            let count = stream.read(&buffer, maxLength: buffer.count)
            if count <= 0 { break }
            data.append(buffer, count: count)
        }
        return data
    }
}
