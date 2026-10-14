# ÇEMBER: iOS / App Store Build Guide

How to ship the same game that's on Google Play to the Apple App Store.

---

## 1. What the game is (and why it matters for iOS)

| Layer | What it is | iOS impact |
|---|---|---|
| **Game** | React 19 + Vite + Tailwind single-page app in `cember_webapp_src/` (~13.5k lines TS). Physics and rendering run on an HTML `<canvas>` (`GameCanvas.tsx`). Sound is synthesized with Web Audio (`utils/audio.ts`). | Runs in WKWebView as-is. **No game logic needs to be rewritten.** |
| **Android shell** | Custom Kotlin "Volkan Web2Android" WebView host in `app/` (asset loader, RPC bridge, splash, immersive mode). | **Does not carry over to iOS.** It needs a new native host. |
| **Native bridge** | `VolkanBridgeManager` (vibrate, share, clipboard…) | The shipped bundle never calls it (`VolkanBridge` appears 0 times in `index-*.js`), so the iOS host doesn't need a bridge. |
| **Multiplayer** | `utils/multiplayer.ts`: MQTT over `wss://` to public brokers (HiveMQ, EMQX) plus `BroadcastChannel`. | Works in WKWebView (TLS, so ATS is fine; `BroadcastChannel` needs iOS 15.4+). `server.ts` (Express/SSE) is **not used** by the shipped bundle. |
| **Tilt control** | `utils/gyroscope.ts` already calls `DeviceOrientationEvent.requestPermission()` (the iOS path). | Works. The iOS host must grant motion permission (see §4). |
| **Shop / currency** | Items cost `priceStars`, which are earned in-game. No real money. | **No In-App Purchase / StoreKit needed.** |
| **External network** | Google Fonts (`Outfit`), `flagcdn.com` flag images. | First launch offline shows fallback font and broken flags. Bundle them locally (§5). |
| **Mic / analytics** | `app-config.json` declares `microphoneEnabled: true` and `analytics: true`, but the code never calls `getUserMedia` and has no analytics SDK. | **Don't add a microphone permission on iOS.** Apple rejects apps that request permissions they don't use. |

**Conclusion:** reuse the web build unchanged and put it in an iOS WebView host. Recommended host: **Capacitor** (§3). It serves bundled files over a custom `capacitor://localhost` origin, the same idea as Android's `appassets.androidplatform.net`, and generates the Xcode project, icons and splash screen. A hand-written Swift `WKWebView` + `WKURLSchemeHandler` shell is the alternative if you want an iOS twin of the Volkan shell. It's about 300 lines, but you maintain it yourself.

---

## 2. Prerequisites

- A Mac with **Xcode 26 or newer** (this machine has Xcode 27.0, which is fine). App Store uploads must be built with the iOS 26 SDK or later.
- Node.js 20+ (this machine has v24.8.0).
- **Apple Developer Program** membership ($99/year), enrolled as the person or company that will appear as the seller (Volkan Olgaç).
- An iPhone for real-device testing. Tilt control and audio behave differently on the simulator.

---

## 3. Create the iOS project (Capacitor)

> **Status:** done. The project lives in `cember_webapp_src/ios/` (Capacitor 8.5, Swift Package Manager), and §4–§5 are applied. It was verified running on the iPhone 17 simulator (iOS 26). This section documents how it was set up.

```bash
cd cember_webapp_src
npm install
npm install @capacitor/core @capacitor/ios @capacitor/splash-screen @capacitor/haptics @fontsource/outfit
npm install -D @capacitor/cli @capacitor/assets
npx cap init "ÇEMBER" com.volkanolgac.cember --web-dir dist
```

> Bundle ID: pick it once and never change it. Reusing the Android `applicationId` (`com.volkanolgac.cemberwebapp`) is fine. A cleaner `com.volkanolgac.cember` also works.

Replace the generated `capacitor.config.ts` with:

```ts
import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.volkanolgac.cember',
  appName: 'ÇEMBER',
  webDir: 'dist',
  backgroundColor: '#0B0F19',
  ios: {
    contentInset: 'never',
    scrollEnabled: false,         // no rubber-band bounce during play
    allowsLinkPreview: false,
  },
  plugins: {
    SplashScreen: { launchShowDuration: 800, backgroundColor: '#0B0F19', showSpinner: false },
    // Hides the status bar and the home indicator (Capacitor 8 built-in plugin)
    SystemBars: { hidden: true },
  },
};
export default config;
```

Build and add the iOS platform:

```bash
npm run build
npx cap add ios
npx cap sync ios
```

Generate the icon from the existing artwork. Apple needs 1024×1024 with **no transparency**; `--iconBackgroundColor` flattens the alpha:

```bash
mkdir -p assets && sips -z 1024 1024 ../cember-icon.png --out assets/icon-only.png
npx capacitor-assets generate --ios --iconBackgroundColor '#0B0F19' --splashBackgroundColor '#0B0F19'
```

> ⚠️ **Replace the icon before release.** `cember-icon.png` is only 512×512 (upscaled, so slightly soft), and its "ÇEMBER" wordmark is cut off at the bottom edge. Export a clean 1024×1024 PNG, save it as `assets/icon-only.png`, and re-run the command.
>
> The splash (`ios/App/App/Assets.xcassets/Splash.imageset/*.png`) is the icon centered on `#0B0F19`, made with `sips --padToHeightWidth 2732 2732 --padColor 0B0F19`.

Open it in Xcode:

```bash
npx cap open ios
```

Day-to-day loop after any game change: `npm run build && npx cap sync ios`, then Run in Xcode.

---

## 4. Native iOS settings (Xcode)

In **App target → Signing & Capabilities**, select your Team and keep "Automatically manage signing" on.

In **App target → General**:
- *(All of the settings below are already applied in the project.)*
- Deployment target: **iOS 15.4** (needed for `BroadcastChannel`).
- Supported destinations: **iPhone only** is simplest (no iPad screenshots or iPad layout review). Add iPad only if you've tested the layout there.
- Device orientation: **Portrait** only, matching `orientationMode: PORTRAIT`.
- Check **Requires full screen**.

Add to `ios/App/App/Info.plist`:

```xml
<key>ITSAppUsesNonExemptEncryption</key><false/>   <!-- only standard HTTPS/WSS: skips export-compliance questions -->
<key>UIStatusBarHidden</key><true/>
<key>UIViewControllerBasedStatusBarAppearance</key><true/>
```

Do **not** add `NSMicrophoneUsageDescription`, `NSCameraUsageDescription` or location keys. The game doesn't use them.

**Gameplay-critical tweaks:** the paddle sits at the bottom of the screen, where iOS's home-indicator swipe lives. `SystemBars: { hidden: true }` (in the config) hides the status bar and home indicator. Capacitor 8 owns `prefersHomeIndicatorAutoHidden`, so don't override it in Swift: it fails to compile. `ios/App/App/GameViewController.swift` handles the rest:

```swift
import UIKit
import WebKit
import Capacitor

class GameViewController: CAPBridgeViewController {
    // Require a second swipe to leave the app mid-game
    override var preferredScreenEdgesDeferringSystemGestures: UIRectEdge { [.bottom, .top] }

    override func capacitorDidLoad() {
        webView?.scrollView.bounces = false
        webView?.allowsBackForwardNavigationGestures = false
        webView?.uiDelegate = self   // grants the tilt-control permission below
    }
}

extension GameViewController: WKUIDelegate {
    // Lets DeviceOrientationEvent.requestPermission() in gyroscope.ts succeed
    func webView(_ webView: WKWebView,
                 requestDeviceOrientationAndMotionPermissionFor origin: WKSecurityOrigin,
                 initiatedByFrame frame: WKFrameInfo,
                 decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        decisionHandler(.grant)
    }
}
```

It's wired in `SceneDelegate.swift` (`window?.rootViewController = GameViewController()`), which is what Capacitor 8 actually uses, and in `Main.storyboard`.

> Replacing the `uiDelegate` disables Capacitor's JS `alert()`/`confirm()` UI. The game doesn't use them. If it ever does, subclass Capacitor's delegate instead.

**Audio:** WKWebView's Web Audio follows the ringer switch by default, so it's silent in silent mode, like most casual games. That's acceptable. If you want sound to always play, set `AVAudioSession.sharedInstance().setCategory(.playback)` in `AppDelegate`.

---

## 5. Web-side changes required for iPhone

These are small changes in `cember_webapp_src/`. They also benefit the Android build.

1. **Safe areas (notch / Dynamic Island).** ✅ Applied. `index.html` uses `viewport-fit=cover`, but no CSS read `env(safe-area-inset-*)`, so the HUD rendered under the Dynamic Island. The padding goes on the `h-[100dvh]` app container in `App.tsx` (`pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]`). It must **not** go on `#root`: that makes the page taller than the screen, the whole page then scrolls, and the scroll offset carries into the game screen. `GameCanvas` sizes itself from its container, so the canvas adapts automatically.

2. **Hide the fullscreen button.** ✅ Applied. `isFullscreenSupported()` in `utils/fullscreen.ts` returns false inside the native app, where WKWebView still reports fullscreen as enabled. It also returns false where the API is missing. `MainMenu` and `GameHUD` hide the button when it returns false.

3. **Bundle the font and flags offline.** ✅ Applied. The Outfit font comes from `@fontsource/outfit` (imported in `main.tsx`), and the Google Fonts `<link>` tags are gone. The 40 flags are in `public/flags/`, and `CountryFlag.tsx` loads `flags/${code}.png` (a relative path, so it works under both `capacitor://localhost` and Android's asset loader). This also removes Google and flagcdn from your privacy disclosures.

4. **Optional, not done yet (helps App Review guideline 4.2):** add native haptics (`@capacitor/haptics` is already installed) with `@capacitor/haptics` on paddle hits and goals. A "native feel" makes the app less likely to be judged a "repackaged website".

---

## 6. Test

```bash
npx cap run ios   # pick a simulator, or a connected iPhone
```

Checklist (on a **real iPhone**):
- [ ] HUD isn't clipped by the Dynamic Island; the bottom paddle area isn't under the home indicator
- [ ] Swiping up from the bottom during play doesn't exit (needs a second swipe)
- [ ] Sound plays after the first tap
- [ ] Tilt control: enable it, accept the permission, then calibrate and play
- [ ] Multiplayer: host on iPhone, join from the Android build with the room code (cross-platform play works, since both use the same MQTT brokers)
- [ ] Airplane mode: single-player, Adventure and Tournament modes still work
- [ ] Progress, stars and best combo survive an app kill and relaunch (stored in `localStorage` inside WKWebView)

---

## 7. Archive and upload

1. In Xcode, select **Any iOS Device (arm64)**, then **Product → Archive**.
2. In Organizer, choose **Distribute App → App Store Connect → Upload**.
3. The build appears in App Store Connect → TestFlight after processing (about 10–30 minutes). Test it there first.

Bump the version every upload: **Version** (`MARKETING_VERSION`, e.g. 1.0.0) and **Build** (`CURRENT_PROJECT_VERSION`, must increase: 1, 2, 3…).

CLI alternative (useful for CI):
```bash
cd ios/App
xcodebuild -workspace App.xcworkspace -scheme App -configuration Release \
  -archivePath build/Cember.xcarchive -destination 'generic/platform=iOS' archive
xcodebuild -exportArchive -archivePath build/Cember.xcarchive \
  -exportOptionsPlist ExportOptions.plist -exportPath build/ipa
```
(Capacitor 8+ uses Swift Package Manager. If your version generated CocoaPods instead, use `App.xcworkspace` as shown. Otherwise use `-project App.xcodeproj`.)

---

## 8. App Store Connect listing

| Item | What to enter |
|---|---|
| App name | ÇEMBER (must be unique on the store; add a subtitle if it's taken) |
| Category | Games → Arcade (secondary: Sports) |
| Age rating | Answer the questionnaire. No violence, gambling or UGC chat, so it should come out 4+. |
| Privacy policy URL | Required. Host `generated/privacy-policy.html` publicly (e.g. GitHub Pages). |
| App Privacy ("nutrition label") | If you do the §5 offline changes: **Data Not Collected**. Player name and team pass through public MQTT brokers only during a live match, aren't stored or linked to identity, and aren't collected by you. Disclose it in the privacy policy anyway. **Fix the policy text**, which currently claims microphone and analytics data, before reusing it. |
| Screenshots | **6.9" iPhone** (1320×2868) is required; Apple scales it for smaller devices. Capture from the iPhone 17 Pro Max simulator with ⌘S. Add iPad 13" only if you ship iPad. |
| Support URL | Any page with contact info (`volkanolgac@gmail.com`) |
| Review notes | "Offline arcade game, fully bundled. Multiplayer: tap Multiplayer → Create Room and join with the 4–6 digit code from a second device." |

---

## 9. App Review risks specific to this app

| Guideline | Risk | Mitigation |
|---|---|---|
| **4.2 Minimum functionality** (web wrappers) | Medium-low. It's a complete, locally bundled game, not a website shell. | Bundle the font and flags (§5.3), add haptics (§5.4), make sure it works offline. |
| **5.1.1 Data collection / permissions** | High if you copy the Android config | No mic permission. Privacy label and policy must match reality. |
| **2.1 App completeness** | Multiplayer depends on public brokers being reachable | Explain how to test in Review Notes. Public brokers have no SLA, so consider a paid or self-hosted MQTT broker for production. |
| **4.0 Design** | Content under the Dynamic Island, or fullscreen button that does nothing | §5.1 and §5.2 |
| **Public MQTT brokers** (not a review rule, but a production concern) | Anyone who knows a room code topic can read or inject messages | Acceptable for a casual game. Move to a private broker with auth before scaling. |

---

## 10. Quick reference

```bash
# once
cd cember_webapp_src && npm install && npx cap add ios

# every release
npm run build && npx cap sync ios && npx cap open ios
# Xcode: bump Build number → Product → Archive → Distribute → App Store Connect
```
