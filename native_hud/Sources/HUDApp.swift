import SwiftUI
import AppKit

@main
struct HUDApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    var body: some Scene {
        Settings { EmptyView() } // Hide default window
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!

    func applicationDidFinishLaunching(_ notification: Notification) {
        let screenFrame = NSScreen.main?.frame ?? .zero
        
        window = NSWindow(
            contentRect: screenFrame,
            styleMask: [.borderless, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        
        window.isOpaque = false
        window.backgroundColor = .clear
        window.level = .mainMenu + 1 // Higher than dock and menu bar
        window.ignoresMouseEvents = true
        window.hasShadow = false
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        
        let contentView = HUDView()
        let hostingView = NSHostingView(rootView: contentView)
        hostingView.frame = screenFrame
        window.contentView = hostingView
        
        window.makeKeyAndOrderFront(nil)
        NSApp.setActivationPolicy(.accessory) // Hide from dock
    }
}
