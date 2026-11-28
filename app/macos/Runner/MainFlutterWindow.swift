import Cocoa
import FlutterMacOS

class MainFlutterWindow: NSWindow {
  override func awakeFromNib() {
    let flutterViewController = FlutterViewController()
    // A thin strip with room for the check-in panel, kept above other windows.
    var windowFrame = self.frame
    windowFrame.size = NSSize(width: 840, height: 290)
    self.contentViewController = flutterViewController
    self.setFrame(windowFrame, display: true)
    self.level = .floating
    self.title = "MuFuse strip"

    RegisterGeneratedPlugins(registry: flutterViewController)

    super.awakeFromNib()
  }
}
