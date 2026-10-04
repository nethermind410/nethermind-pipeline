import AppKit
import Foundation

let out = CommandLine.arguments[1]
let items = [
    ("01", "WHY DOES THIS LOOK\n\"WRONG\"?", 82),
    ("02", "DENSE\nBUSY\nTINY TEXT", 88),
    ("03", "\"BEHIND\"?", 110),
    ("04", "BUT THAT'S THE\nINTERESTING PART.", 64),
    ("05", "WHY?", 140),
    ("06", "IT'S CULTURE.", 110),
    ("07", "DESIGN IS NOT\nOBJECTIVE.", 64),
    ("08", "WHAT FEELS CLEAN\nCAN FEEL WRONG.", 64),
    ("09", "MAYBE IT'S YOUR\nDEFINITION OF NORMAL.", 58)
]

for (name, text, size) in items {
    let width = 1080
    let height = 1920
    let image = NSImage(size: NSSize(width: width, height: height))
    image.lockFocus()

    NSColor.clear.setFill()
    NSBezierPath(rect: NSRect(x: 0, y: 0, width: width, height: height)).fill()

    let font = NSFont.boldSystemFont(ofSize: CGFloat(size))
    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = .center
    paragraph.lineSpacing = 8

    let attrs: [NSAttributedString.Key: Any] = [
        .font: font,
        .foregroundColor: NSColor.white,
        .paragraphStyle: paragraph,
        .strokeColor: NSColor.black,
        .strokeWidth: -5
    ]

    let attributed = NSAttributedString(string: text, attributes: attrs)
    let rect = NSRect(x: 60, y: 620, width: width - 120, height: 700)
    attributed.draw(in: rect)

    image.unlockFocus()

    guard let tiff = image.tiffRepresentation,
          let rep = NSBitmapImageRep(data: tiff),
          let png = rep.representation(using: .png, properties: [:])
    else { continue }

    try? png.write(to: URL(fileURLWithPath: "\(out)/\(name).png"))
}
