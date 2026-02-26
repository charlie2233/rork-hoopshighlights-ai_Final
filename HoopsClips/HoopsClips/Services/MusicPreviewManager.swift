import Foundation
import AVFoundation

@Observable
@MainActor
final class MusicPreviewManager {
    var isPlaying = false
    var currentTrack: MusicTrack?
    
    private var audioPlayer: AVAudioPlayer?
    
    func togglePreview(for track: MusicTrack) {
        if currentTrack == track && isPlaying {
            stopPreview()
        } else {
            playPreview(for: track)
        }
    }
    
    func stopPreview() {
        audioPlayer?.stop()
        isPlaying = false
        currentTrack = nil
    }
    
    private func playPreview(for track: MusicTrack) {
        guard let filename = track.filename else { return }
        
        // Handle flattened bundle resources or subdirectory structure
        var url = Bundle.main.url(forResource: filename, withExtension: nil)
        if url == nil {
             url = Bundle.main.url(forResource: filename, withExtension: nil, subdirectory: "Resources/Audio")
        }
        
        if url == nil {
            // Try splitting name/ext
            let name = (filename as NSString).deletingPathExtension
            let ext = (filename as NSString).pathExtension
            url = Bundle.main.url(forResource: name, withExtension: ext)
            
            if url == nil {
                url = Bundle.main.url(forResource: name, withExtension: ext, subdirectory: "Resources/Audio")
            }
        }
        
        guard let musicURL = url else {
            print("Preview file not found: \(filename)")
            return
        }
        
        do {
            try AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
            try AVAudioSession.sharedInstance().setActive(true)
            
            audioPlayer = try AVAudioPlayer(contentsOf: musicURL)
            audioPlayer?.volume = 0.5
            audioPlayer?.numberOfLoops = -1 // Loop preview
            audioPlayer?.play()
            
            currentTrack = track
            isPlaying = true
        } catch {
            print("Failed to play preview: \(error)")
        }
    }
}
