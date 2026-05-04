import SwiftUI

struct HUDView: View {
    @State private var status = "IDLE"
    @State private var user_input = ""
    @State private var intel_card_title = ""
    @State private var intel_card_body = ""
    @State private var show_intel_card = false
    @State private var orbColor = Color(red: 0.5, green: 0.2, blue: 1.0)
    
    @State private var rotation: Double = 0
    @State private var pulse: CGFloat = 1.0
    
    let timer = Timer.publish(every: 0.1, on: .main, in: .common).autoconnect()
    
    var body: some View {
        ZStack {
            VikingGrid()
                .stroke(orbColor.opacity(0.05), lineWidth: 0.5)
                .edgesIgnoringSafeArea(.all)
            
            // Peripheral Technical Greebles
            ZStack {
                TechnicalCorner(align: .topLeading, label: "SYS_LINK", data: ["CORE: \(status)", "STBL: 99.8%", "V_LNK: ON"])
                TechnicalCorner(align: .topTrailing, label: "TELEMETRY", data: ["CPU: 14%", "MEM: 4.2GB", "LAT: 8ms"])
                TechnicalCorner(align: .bottomLeading, label: "NEURAL_NET", data: ["WHISPER_BASE", "MLX_ACCEL", "INT_8"])
                TechnicalCorner(align: .bottomTrailing, label: "OS_ROOT", data: ["MACOS_26.3", "FRIDAY_v3.5", "ROOT_AUTH"])
            }
            
            // The Core
            ZStack {
                Circle()
                    .stroke(orbColor.opacity(0.2), lineWidth: 1)
                    .frame(width: 320, height: 320)
                    .rotationEffect(.degrees(rotation))
                
                Circle()
                    .stroke(orbColor.opacity(0.1), style: StrokeStyle(lineWidth: 1, lineCap: .round, dash: [2, 10]))
                    .frame(width: 340, height: 340)
                    .rotationEffect(.degrees(-rotation * 0.5))
                
                TimelineView(.animation) { timeline in
                    Canvas { context, size in
                        let time = timeline.date.timeIntervalSinceReferenceDate
                        drawFluidOrb(context: context, size: size, time: time)
                    }
                    .frame(width: 250, height: 250)
                }
                .blur(radius: 5)
                .shadow(color: orbColor.opacity(0.5), radius: 30)
            }
            .scaleEffect(pulse)
            
            if show_intel_card {
                VStack(alignment: .leading, spacing: 10) {
                    Text(intel_card_title)
                        .font(.system(size: 14, weight: .black, design: .monospaced))
                        .foregroundColor(.white)
                    Divider().background(Color.white.opacity(0.3))
                    Text(intel_card_body)
                        .font(.system(size: 12, weight: .light, design: .monospaced))
                        .foregroundColor(.white.opacity(0.9))
                }
                .padding(20)
                .frame(width: 300)
                .background(.ultraThinMaterial)
                .cornerRadius(10)
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(Color.blue.opacity(0.3), lineWidth: 1))
                .offset(x: 350, y: 0)
                .transition(.move(edge: .trailing).combined(with: .opacity))
            }
            
            VStack {
                Spacer()
                if !user_input.isEmpty {
                    Text(user_input.uppercased())
                        .font(.system(size: 16, weight: .bold, design: .monospaced))
                        .foregroundColor(.cyan)
                        .padding(.bottom, 5)
                        .tracking(4)
                        .opacity(0.8)
                }
                Rectangle()
                    .fill(orbColor.opacity(0.3))
                    .frame(width: 300, height: 1)
                    .padding(.bottom, 20)
            }
        }
        .onReceive(timer) { _ in
            updateState()
            withAnimation(.linear(duration: 0.1)) {
                rotation += 2
            }
        }
    }
    
    func drawFluidOrb(context: GraphicsContext, size: CGSize, time: Double) {
        let center = CGPoint(x: size.width / 2, y: size.height / 2)
        let count = 8
        for i in 0..<count {
            let angle = (Double(i) / Double(count)) * .pi * 2 + time
            let x = center.x + cos(angle) * 20 * sin(time * 0.5)
            let y = center.y + sin(angle) * 20 * cos(time * 0.8)
            let rect = CGRect(x: x - 40, y: y - 40, width: 80, height: 80)
            context.fill(Path(ellipseIn: rect), with: .color(orbColor.opacity(0.4)))
        }
        let coreRect = CGRect(x: center.x - 30, y: center.y - 30, width: 60, height: 60)
        context.fill(Path(ellipseIn: coreRect), with: .color(.white.opacity(0.8)))
    }
    
    func updateState() {
        let path = "/Users/bhargav/AI/friday/native_hud/Resources/hud_state.json"
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else { return }
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }
        self.status = (json["status"] as? String) ?? "IDLE"
        self.user_input = (json["user_input"] as? String) ?? ""
        if let intel = json["intel_card"] as? [String: String] {
            self.intel_card_title = intel["title"] ?? ""
            self.intel_card_body = intel["body"] ?? ""
            withAnimation(.spring()) { self.show_intel_card = true }
        } else {
            withAnimation { self.show_intel_card = false }
        }
        if status == "THINKING" {
            orbColor = .red
            pulse = 1.05 + 0.05 * sin(Date().timeIntervalSince1970 * 10)
        } else if status == "SPEAKING" {
            orbColor = .orange
            pulse = 1.0 + 0.02 * sin(Date().timeIntervalSince1970 * 5)
        } else {
            orbColor = Color(red: 0.5, green: 0.2, blue: 1.0)
            pulse = 1.0
        }
    }
}

struct TechnicalCorner: View {
    let align: Alignment
    let label: String
    let data: [String]
    var body: some View {
        VStack(alignment: align == .topLeading || align == .bottomLeading ? .leading : .trailing, spacing: 2) {
            Text(label)
                .font(.system(size: 8, weight: .black, design: .monospaced))
                .padding(.horizontal, 4)
                .background(Color.purple.opacity(0.3))
                .foregroundColor(.white)
            ForEach(data, id: \.self) { line in
                Text(line).font(.system(size: 9, design: .monospaced)).foregroundColor(.purple.opacity(0.7))
            }
        }
        .padding(40)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: align)
    }
}

struct VikingGrid: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let step: CGFloat = 50
        for x in stride(from: 0, through: rect.width, by: step) {
            path.move(to: CGPoint(x: x, y: 0)); path.addLine(to: CGPoint(x: x, y: rect.height))
        }
        for y in stride(from: 0, through: rect.height, by: step) {
            path.move(to: CGPoint(x: 0, y: y)); path.addLine(to: CGPoint(x: rect.width, y: y))
        }
        return path
    }
}
