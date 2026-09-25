using GibberishRewriter.App.Win;

namespace GibberishRewriter.App.Tests;

public class StartNoticeTests
{
    private const int Accepts = 5;
    private const int Busy = 2;

    [Fact]
    public void Shows_at_once_when_the_taskbar_exists_and_Windows_accepts_notifications() =>
        Assert.True(StartNotice.ShouldShow(taskbarExists: true, Accepts, waitedMs: 0));

    [Theory]
    [InlineData(false, Accepts)]
    [InlineData(true, Busy)]
    [InlineData(true, 0)]
    public void Waits_while_the_taskbar_is_missing_or_Windows_holds_notifications_back(bool taskbarExists, int state) =>
        Assert.False(StartNotice.ShouldShow(taskbarExists, state, StartNotice.MaxWaitMs - StartNotice.PollIntervalMs));

    [Fact]
    public void Shows_anyway_once_the_longest_wait_has_passed() =>
        Assert.True(StartNotice.ShouldShow(taskbarExists: false, Busy, StartNotice.MaxWaitMs));

    [IntegrationFact]
    public void Windows_reports_the_taskbar_and_a_notification_state_on_this_desktop()
    {
        Assert.True(StartNotice.TaskbarExists());
        Assert.InRange(StartNotice.NotificationState(), 1, 7);
    }
}
