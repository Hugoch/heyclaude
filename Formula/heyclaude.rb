# Homebrew Cask formula for HeyClaude
# Place this in your homebrew-heyclaude tap repository

cask "heyclaude" do
  version "0.1.0"
  sha256 "REPLACE_WITH_SHA256"

  url "https://github.com/GITHUB_USERNAME/heyclaude/releases/download/v#{version}/HeyClaude-#{version}.zip"
  name "HeyClaude"
  desc "macOS menubar app for Claude Code notifications"
  homepage "https://github.com/GITHUB_USERNAME/heyclaude"

  depends_on macos: ">= :monterey"

  app "HeyClaude.app"

  postflight do
    # Install Claude Code hook
    system_command "#{appdir}/HeyClaude.app/Contents/MacOS/HeyClaude",
                   args: ["--install-hook"],
                   print_stderr: false,
                   must_succeed: false
  end

  zap trash: [
    "~/.heyclaude",
    "~/Library/Preferences/com.heyclaude.plist",
  ]
end
