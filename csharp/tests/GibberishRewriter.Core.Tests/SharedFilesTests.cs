namespace GibberishRewriter.Core.Tests;

public class SharedFilesTests
{
    [Fact]
    public void Shared_folder_is_copied_next_to_the_tests()
    {
        var readme = SharedFiles.PathOf("README.md");
        Assert.True(File.Exists(readme), $"Missing {readme}");
    }
}
