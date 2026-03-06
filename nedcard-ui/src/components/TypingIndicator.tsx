export default function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 px-5 py-3.5 mr-auto
                    bg-ned-slate/50 border border-white/[0.06]
                    rounded-2xl rounded-bl-sm w-fit">
      {[0, 1, 2].map(i => (
        <div
          key={i}
          className="w-2 h-2 rounded-full bg-ned-muted dot-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  )
}
