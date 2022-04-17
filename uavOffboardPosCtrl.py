#!/usr/bin/env python

from __future__ import division

PKG = 'px4'

import rospy
import math
import numpy as np

from geometry_msgs.msg import PoseStamped, Quaternion
from mavros_test_common import MavrosTestCommon
from pymavlink import mavutil
from std_msgs.msg import Header
from threading import Thread
from tf.transformations import quaternion_from_euler


class OffboardPosCtrl(MavrosTestCommon):
    """
    Test flying a path in offboard control by sending position
    setpoints via Mavros

    Setpoints must reach within certain time. 
    """

    def setUp(self):
        super(OffboardPosCtrl, self).setUp()

        self.pos = PoseStamped()
        self.radius = 1

        self.pos_sp_pub = rospy.Publisher(
            'mavros/setpoint_position/local', PoseStamped, queue_size=1)
        
        # send SP in separate thread to prevent failsafe
        self.pos_thread = Thread(target=self.send_pos, args=())
        self.pos_thread.daemon = True
        self.pos_thread.start()

    def tearDown(self):
        return super(OffboardPosCtrl, self).tearDown()

    ###
    # Helper Methods
    ###
    def send_pos(self):
        rate = rospy.Rate(10) #Hz
        self.pos.header = Header()
        self.pos.header.frame_id = "base_footprint"

        while not rospy.is_shutdown():
            self.pos.header.stamp = rospy.Time.now()
            self.pos_sp_pub.publish(self.pos)
            try:
                rate.sleep()
            except rospy.ROSInterruptException:
                pass

    def is_at_position(self, x, y, z, offset):
        """
        offset: in meters (m)
        """
        rospy.logdebug(
            "current position | x:{0:.2f}, y{1:.2f}, z{2:.2f}".format(
                self.local_position.pose.position.x,
                self.local_position.pose.position.y,
                self.local_position.pose.position.z
                )
        )

        desired = np.array((x, y, z))
        pos = np.array((self.local_position.pose.position.x,
        self.local_position.pose.position.y,
        self.local_position.pose.position.z))
        return np.linalg.norm(desired - pos) < offset

    def reach_position(self, x, y, z, timeout):
        """
        timeout(int): in seconds (s)
        """
        self.pos.pose.position.x = x
        self.pos.pose.position.y = y
        self.pos.pose.position.z = z
        rospy.loginfo(
            "attempting to reach position | x:{0}, y:{1}, z:{2} | current position x: {3:.2f}, y: {4:.2f}, z: {5:.2f}". 
            format(x, y, z, 
            self.local_position.pose.position.x,
            self.local_position.pose.position.y,
            self.local_position.pose.position.z))

        yaw_deg = 0 #North
        yaw = math.radians(yaw_deg)
        quaternion = quaternion_from_euler(0, 0, yaw)
        self.pos.pose.orientation = Quaternion(*quaternion)

        # does it reach the position in 'timeout' seconds?
        loop_freq = 2 #Hz
        rate = rospy.Rate(loop_freq)
        reached = False
        for i in xrange(timeout * loop_freq):
            if self.is_at_position(self.pos.pose.position.x,
            self.pos.pose.position.y,
            self.pos.pose.position.z, self.radius):
                rospy.loginfo("position reached | seconds: {0} of {1}".format(
                i / loop_freq, timeout))
                reached = True
                break
            
            try:
                rate.sleep()
            except rospy.ROSException as e:
                self.fail(e)

        self.assertTrue(reached, (
            "took too long to get into position | current position x:{0:.2f}, y:{1:.2f}, z:{2:.2f} | timeout(seconds): {3}".format(self.local_position.pose.position.x,
            self.local_position.pose.position.y,
            self.local_position.pose.position.z, timeout)))

    ###
    # Test method
    ###
    def test_posctrl(self):
        """
        Testing offboard position control
        """

        # make sure the simulation is ready to start the mission
        self.wait_for_topics(60)
        self.wait_for_landed_state(mavutil.mavlink.MAV_LANDED_STATE_ON_GROUND, 10, -1)
        self.log_topic_vars()
        self.set_mode("OFFBOARD", 5) # to change to the desired mode
        self.set_arm(True, 5) # arming the UAV

        rospy.loginfo("running mission")
        
        # change position setpoints here
        positions = ((0, 0, 0), (50, 50, 20), (50, -50, 20), (-50, -50, 20),
                     (0, 0, 20))
        
        for i in xrange(len(positions)):
            self.reach_position(positions[i][0],
            positions[i][1],
            positions[i][2], 45)
            
        self.set_mode("AUTO.LAND", 5)
        self.wait_for_landed_state(mavutil.mavlink.MAV_LANDED_STATE_ON_GROUND, 45, 0)
        self.set_arm(False, 5) # disarming the UAV


if __name__ == '__main__':
    import rostest 
    rospy.init_node('test_node', anonymous=True)

    rostest.rosrun(PKG, 'uavOffboardPosCtrl', OffboardPosCtrl)