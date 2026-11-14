rule Demo_Macro_Marker {
    strings:
        $a = "PHISH_DEMO_MARKER"
        $b = "AutoOpen" nocase
    condition:
        any of them
}
