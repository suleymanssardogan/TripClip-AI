import SwiftUI
import UIKit

/// TripClip palette. Values mirror web/src/app/globals.css and adapt
/// to system appearance without view-specific color branches.
enum AppColors {

    private static func dynamic(dark: (Double, Double, Double), light: (Double, Double, Double)) -> Color {
        Color(UIColor { traits in
            let rgb = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(red: rgb.0 / 255, green: rgb.1 / 255, blue: rgb.2 / 255, alpha: 1)
        })
    }

    // MARK: - Ground

    static let background   = dynamic(dark: (18, 27, 34),  light: (248, 250, 252))
    static let surface      = dynamic(dark: (27, 38, 47),  light: (255, 255, 255))
    static let surface2     = dynamic(dark: (37, 49, 59),  light: (241, 245, 248))
    static let border       = dynamic(dark: (60, 76, 87),  light: (226, 232, 238))
    static let borderStrong = dynamic(dark: (85, 103, 115), light: (197, 207, 216))

    // MARK: - Text

    static let text          = dynamic(dark: (245, 248, 250), light: (24, 37, 49))
    static let textSecondary = dynamic(dark: (183, 196, 205), light: (84, 101, 115))
    static let textTertiary  = dynamic(dark: (148, 165, 177), light: (100, 117, 129))

    // MARK: - Brand accent

    static let accent      = dynamic(dark: (120, 184, 255), light: (26, 103, 185))
    static let accentHover = dynamic(dark: (151, 203, 255), light: (19, 82, 154))
    static let accentText  = dynamic(dark: (151, 203, 255), light: (23, 92, 168))
    static let onAccent    = dynamic(dark: (14, 31, 48),    light: (255, 255, 255))

    // MARK: - Semantic

    static let route       = dynamic(dark: (122, 207, 203), light: (28, 112, 125))
    static let success     = dynamic(dark: (121, 211, 154), light: (34, 123, 81))
    static let warning     = dynamic(dark: (239, 191, 113), light: (151, 99, 29))
    static let destructive = dynamic(dark: (255, 135, 140), light: (186, 54, 60))
}
