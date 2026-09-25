using GibberishRewriter.App.Win;

namespace GibberishRewriter.App.Tests;

/// <summary>An integration test that needs English (US) 04090409 and Arabic (101) 04012C01 installed.</summary>
public sealed class LayoutPairFactAttribute : FactAttribute
{
    public LayoutPairFactAttribute()
    {
        if (!IntegrationFactAttribute.Enabled)
        {
            Skip = $"Windows integration test. Set {IntegrationFactAttribute.Variable}=1 to run it.";
        }
        else if (!LayoutReader.InstalledLayouts().Contains(0x04090409u) || !LayoutReader.InstalledLayouts().Contains(0x04012C01u))
        {
            Skip = "English (US) 04090409 and Arabic (101) 04012C01 aren't both installed.";
        }
    }
}
