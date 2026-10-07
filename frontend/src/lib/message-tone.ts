// A prerecorded CC0 chime. Keep the file's original level and the device volume.
export const MESSAGE_TONE_URL = "/sounds/message.wav"

export const createMessageTone = (source = MESSAGE_TONE_URL) => {
  let audio: HTMLAudioElement | undefined
  const prepare = () => {
    try {
      if (!audio) {
        audio = new Audio(source)
        audio.preload = "auto"
        audio.load()
      }
    } catch {
      audio = undefined
    }
  }
  const play = async (): Promise<boolean> => {
    try {
      prepare()
      if (!audio) return false
      audio.currentTime = 0
      await audio.play()
      return true
    } catch {
      // Autoplay restrictions or an unavailable output must not block chat.
      return false
    }
  }
  const stop = () => audio?.pause()
  return { prepare, play, stop }
}
