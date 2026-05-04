import SwiftUI

struct HUDView: View {
    var body: some View {
        ZStack {
            // High visibility test box
            Color.red.opacity(0.8)
                .frame(width: 200, height: 200)
                .position(x: 150, y: 150)
            
            Text("FRIDAY_BOOT_SEQUENCE")
                .foregroundColor(.white)
                .font(.system(size: 20, weight: .bold, design: .monospaced))
                .position(x: 150, y: 150)
        }
        .edgesIgnoringSafeArea(.all)
    }
}
