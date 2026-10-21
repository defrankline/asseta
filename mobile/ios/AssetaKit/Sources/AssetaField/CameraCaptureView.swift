#if os(iOS)
import AVFoundation
import SwiftUI
import UIKit

/// Full-screen in-app camera (AVFoundation). Returns the photo's original JPEG bytes exactly as
/// produced by the camera (`fileDataRepresentation`), or nil if cancelled. No photo library access.
struct CameraCaptureView: UIViewControllerRepresentable {
    let completion: @MainActor (Data?) -> Void

    func makeUIViewController(context: Context) -> CameraViewController {
        CameraViewController(completion: completion)
    }

    func updateUIViewController(_ controller: CameraViewController, context: Context) {}
}

@MainActor
final class CameraViewController: UIViewController, @preconcurrency AVCapturePhotoCaptureDelegate {
    private let completion: @MainActor (Data?) -> Void
    private let runner = CaptureSessionRunner()
    private var session: AVCaptureSession { runner.session }
    private let output = AVCapturePhotoOutput()
    private var preview: AVCaptureVideoPreviewLayer?
    private let shutter = UIButton(type: .system)
    private let message = UILabel()
    private var finished = false

    init(completion: @escaping @MainActor (Data?) -> Void) {
        self.completion = completion
        super.init(nibName: nil, bundle: nil)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        guard configureSession() else {
            showMessage("The camera is not available on this device.")
            addCancelButton()
            return
        }
        let layer = AVCaptureVideoPreviewLayer(session: session)
        layer.videoGravity = .resizeAspect
        view.layer.addSublayer(layer)
        preview = layer
        shutter.setImage(UIImage(systemName: "circle.inset.filled",
                                 withConfiguration: UIImage.SymbolConfiguration(pointSize: 72)), for: .normal)
        shutter.tintColor = .white
        shutter.accessibilityLabel = "Take photo"
        shutter.addTarget(self, action: #selector(takePhoto), for: .touchUpInside)
        shutter.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(shutter)
        NSLayoutConstraint.activate([
            shutter.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            shutter.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -24),
        ])
        addCancelButton()
        showMessage("Fill the frame with the meter display")
        runner.start()
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        preview?.frame = view.bounds
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        runner.stop()
    }

    private func configureSession() -> Bool {
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
              let input = try? AVCaptureDeviceInput(device: device) else { return false }
        session.beginConfiguration()
        session.sessionPreset = .photo
        guard session.canAddInput(input), session.canAddOutput(output) else {
            session.commitConfiguration()
            return false
        }
        session.addInput(input)
        session.addOutput(output)
        session.commitConfiguration()
        return true
    }

    private func addCancelButton() {
        let cancel = UIButton(type: .system)
        cancel.setTitle("Cancel", for: .normal)
        cancel.tintColor = .white
        cancel.titleLabel?.font = .preferredFont(forTextStyle: .headline)
        cancel.addTarget(self, action: #selector(cancelTapped), for: .touchUpInside)
        cancel.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(cancel)
        NSLayoutConstraint.activate([
            cancel.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 20),
            cancel.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 12),
        ])
    }

    private func showMessage(_ text: String) {
        message.text = text
        message.textColor = .white
        message.textAlignment = .center
        message.numberOfLines = 0
        message.translatesAutoresizingMaskIntoConstraints = false
        if message.superview == nil { view.addSubview(message) }
        NSLayoutConstraint.activate([
            message.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 24),
            message.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -24),
            message.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 56),
        ])
    }

    @objc private func takePhoto() {
        shutter.isEnabled = false
        let settings = output.availablePhotoCodecTypes.contains(.jpeg)
            ? AVCapturePhotoSettings(format: [AVVideoCodecKey: AVVideoCodecType.jpeg])
            : AVCapturePhotoSettings()
        output.capturePhoto(with: settings, delegate: self)
    }

    @objc private func cancelTapped() { finish(nil) }

    func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: (any Error)?) {
        guard error == nil, let data = photo.fileDataRepresentation() else {
            shutter.isEnabled = true
            showMessage("The photo could not be taken. Try again.")
            return
        }
        finish(data)
    }

    private func finish(_ data: Data?) {
        guard !finished else { return }
        finished = true
        completion(data)
    }
}
/// Owns the capture session and starts/stops it on one serial queue (`startRunning` blocks, and
/// Apple requires it off the main thread).
final class CaptureSessionRunner: @unchecked Sendable {
    // @unchecked: `session` is configured on the main thread before `start()` and afterwards only
    // touched on `queue`.
    let session = AVCaptureSession()
    private let queue = DispatchQueue(label: "asseta.camera.session")

    func start() { queue.async { self.session.startRunning() } }
    func stop() { queue.async { self.session.stopRunning() } }
}
#endif
