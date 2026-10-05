import AppKit
import Foundation

let out = CommandLine.arguments[1]

let items = [
    ("01", "WHY DOES THIS LOOK\n\"WRONG\"?", 58, 90),
    ("02", "DENSE  •  BUSY  •  TINY", 42, 90),
    ("03", "BEHIND?", 48, 90),
    ("04", "THE INTERESTING PART", 40, 90),
    ("05", "WHY?", 60, 90),
    ("06", "CULTURE", 52, 90),
    ("07", "DESIGN IS NOT OBJECTIVE", 38, 90),
    ("08", "WHAT FEELS CLEAN\nCAN FEEL WRONG", 38, 90),
    ("09", "YOUR DEFINITION\nOF NORMAL", 44, 90)
]

for (name, text, size, margin) in items {
    let width = 1080
    let height = 1920

    let image = NSImage(size: NSSize(width: width, height: height))
    image.lockFocus()

    NSColor.clear.setFill()
    NSBezierPath(
        rect: NSRect(x: 0, y: 0, width: width, height: height)
    ).fill()

    let font = NSFont.systemFont(
        ofSize: CGFloat(size),
        weight: .bold
    )

    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = .center
    paragraph.lineSpacing = 4

    let attrs: [NSAttributedString.Key: Any] = [
        .font: font,
        .foregroundColor: NSColor.white,
        .paragraphStyle: paragraph,
        .strokeColor: NSColor.black.withAlphaComponent(0.85),
        .strokeWidth: -2.5
    ]

    let attributed = NSAttributedString(
        string: text,
        attributes: attrs
    )

    let rect = NSRect(
        x: CGFloat(margin),
        y: 155,
        width: CGFloat(width - margin * 2),
        height: 260
    )

    attributed.draw(in: rect)

    image.unlockFocus()

    guard
        let tiff = image.tiffRepresentation,
        let rep = NSBitmapImageRep(data: tiff),
        let png = rep.representation(
            using: .png,
            properties: [:]
        )
    else {
        continue
    }

    try? png.write(
        to: URL(fileURLWithPath: "\(out)/\(name).png")
    )
}
