class F2format < Formula
  include Language::Python::Virtualenv

  desc "Shiny new formula"
  homepage "https://github.com/JarryShaw/f2format"
  url "https://files.pythonhosted.org/packages/77/57/50f11e11948db48769328228a6228222205aa0ae820137b8b4ee50d691c3/f2format-0.1.3.post1.tar.gz"
  sha256 "535490102c13825d7ad0eef7530b253c512a62a5c917de886b359cda1c06e19b"

  depends_on "python3"

  def install
    virtualenv_create(libexec, "python3")
    virtualenv_install_with_resources
  end

  test do
    false
  end
end
