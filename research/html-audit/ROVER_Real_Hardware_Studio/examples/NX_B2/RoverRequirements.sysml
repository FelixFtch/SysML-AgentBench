// TEACHING REQUIREMENTS DRAFT. Parser NOT RUN. Not an API response.
package RoverRequirements {
    private import ScalarValues::*;
    requirement def MapNavigation {
        doc /* R-01: 沿已有室内地图在指定站点间行驶。 */
    }
    requirement def LocalStop {
        doc /* R-02: 障碍条件成立时进入停止状态；恢复条件另行审查。 */
    }
    requirement def OfflineOperation {
        doc /* R-03: 基本导航和停止处理不依赖互联网。 */
    }
    requirement def RuntimeTarget {
        doc /* R-04: 规定工作负载下，估算续航不少于2小时。 */
        attribute minimum_h : Real = 2.0;
    }
    requirement def WidthLimit {
        doc /* R-05: 含附件的整车宽度不超过350 mm。 */
        attribute maximum_mm : Real = 350.0;
    }
    requirement def StateVisibility {
        doc /* R-06: 可区分待命、导航、停止和故障状态。 */
    }
}
