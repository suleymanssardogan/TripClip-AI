import SwiftUI
import UIKit

/// TripClip design tokens — dark is the primary ground, light is generated
/// from the same semantic roles (see the web design-system: Ember accent,
/// Route teal, one accent used sparingly). Every color is dynamic so the
/// app follows the system appearance automatically, no separate dark/light
/// call sites anywhere else in the app.
enum AppColors {

    private static func dynamic(dark: (Double, Double, Double), light: (Double, Double, Double)) -> Color {
        Color(UIColor { traits in
            let rgb = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(red: rgb.0 / 255, green: rgb.1 / 255, blue: rgb.2 / 255, alpha: 1)
        })
    }

    // MARK: - Ground

    static let background   = dynamic(dark: (12, 13, 16),   light: (246, 247, 248))
    static let surface      = dynamic(dark: (26, 28, 33),   light: (255, 255, 255))
    static let surface2     = dynamic(dark: (34, 37, 43),   light: (237, 238, 240))
    static let border       = dynamic(dark: (42, 46, 53),   light: (225, 227, 231))
    static let borderStrong = dynamic(dark: (58, 63, 72),   light: (203, 206, 211))

    // MARK: - Text

    static let text          = dynamic(dark: (243, 241, 236), light: (20, 22, 26))
    static let textSecondary = dynamic(dark: (162, 166, 173), light: (82, 86, 93))
    static let textTertiary  = dynamic(dark: (108, 112, 121), light: (130, 134, 141))

    // MARK: - Accent (Ember) — the app's one brand color, used sparingly.
    // `accent` is for solid fills (always paired with `onAccent` text, never
    // white — Ember is too light in both modes to carry white text at AA
    // contrast). `accentText` is the same hue tuned for use as standalone
    // foreground text/icons.

    static let accent      = dynamic(dark: (255, 176, 32), light: (232, 137, 26))
    static let accentHover = dynamic(dark: (255, 195, 82), light: (214, 125, 18))
    static let accentText  = dynamic(dark: (255, 176, 32), light: (168, 82, 0))
    static let onAccent    = dynamic(dark: (26, 18, 6),     light: (26, 18, 6))

    // MARK: - Semantic

    static let route       = dynamic(dark: (63, 217, 196),  light: (12, 117, 104))   // map/route, secondary info
    static let success     = dynamic(dark: (52, 199, 89),   light: (31, 122, 53))
    static let warning     = dynamic(dark: (224, 162, 51),  light: (154, 91, 0))
    static let destructive = dynamic(dark: (255, 69, 58),   light: (215, 0, 21))
}
