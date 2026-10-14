import UIKit
import WebKit
import Capacitor

class GameViewController: CAPBridgeViewController {
    // The paddle sits at the bottom edge: require a second swipe to leave the app mid-game.
    // Status bar and home indicator are hidden via SystemBars { hidden: true } in capacitor.config.ts.
    override var preferredScreenEdgesDeferringSystemGestures: UIRectEdge { [.bottom, .top] }

    override func capacitorDidLoad() {
        webView?.scrollView.bounces = false
        webView?.allowsBackForwardNavigationGestures = false
        webView?.uiDelegate = self
    }
}

extension GameViewController: WKUIDelegate {
    // Lets DeviceOrientationEvent.requestPermission() in gyroscope.ts succeed (tilt control)
    func webView(_ webView: WKWebView,
                 requestDeviceOrientationAndMotionPermissionFor origin: WKSecurityOrigin,
                 initiatedByFrame frame: WKFrameInfo,
                 decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        decisionHandler(.grant)
    }
}
