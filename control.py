#! /usr/bin/env python3
from control_cmd import Inspections

def Singleton(cls):
    instance = {}

    def _singleton_wrapper(*args, **kargs):
        if cls not in instance:
            instance[cls] = cls(*args, **kargs)
        return instance[cls]

    return _singleton_wrapper

def display_version():
    print("version: v1.0.0")

@Singleton
class Control:
    def __init__(self, logger):
        self.ins = Inspections(logger)
        self.print_ = []
        self.logger = logger

    # 检查软件
    def check_software(self):
        print("———— 检查软件 ————")
        buffer = False
        service_bool = True
        services = [
            "drbd",
            "linstor-controller",
            "rtslib-fb-targetctl",
            "linstor-satellite",
            "pacemaker",
            "corosync"
        ]

        for service in services:
            if not self.ins.check_software_(service):
                service_bool = False
        
        if self.ins.check_unattended_upgrades() and self.ins.check_configuration_file():
            buffer = True

        if buffer and service_bool:
            print("通过")
        else:
            self.print_.append(f"检查软件异常")
            print(f"不通过")

    # 检查网络
    def check_network(self):
        print("———— 检查网络 ————")
        buffer = True
        if not self.ins.check_bond_connections():
            self.print_.append(f"检查网络时，Bond 连接情况检查结果异常")
            buffer = False
        if not self.ins.check_bond():
            self.print_.append(f"检查网络时，Bond 检查结果异常")
            buffer = False
        if not self.ins.check_cluster_network():
            self.print_.append(f"检查网络时，集群网络检查结果异常")
            buffer = False
        
        if buffer:
            print("通过")
        else:
            print(f"不通过")

    # 检查 Corosync
    def check_corosync(self):
        print("———— 检查 Corosync ————")
        buffer = True
        if not self.ins.corosync_check():
            self.print_.append(f"检查 Corosync 结果异常")
            buffer = False
        
        if buffer:
            print("通过")
        else:
            print(f"不通过")

    # 检查 pacemaker 集群
    def check_pacemaker_cluster(self):
        print("———— 检查 pacemaker 集群 ————")
        buffer = True
        if not self.ins.check_crm_status():
            buffer = False
        if not self.ins.check_resource_stickiness():
            buffer = False
        if not self.ins.check_value():
            buffer = False
        
        if buffer:
            print("通过")
        else:
            self.print_.append(f"检查 pacemaker 集群异常")
            print(f"不通过")

    # 检查 LINSTOR Controller HA
    def check_linstor_controller_ha(self):
        print("———— 检查 LINSTOR Controller HA ————")
        buffer = True
        if not self.ins.check_database_resource():
            buffer = False
        
        if buffer:
            print("通过")
        else:
            self.print_.append(f"检查 LINSTOR Controller HA 异常")
            print(f"不通过")

    # 检查 LINSTOR
    def check_linstor(self):
        print("———— 检查 LINSTOR ————")
        buffer = True
        if not self.ins.linstor_check():
            buffer = False
        if not self.ins.linstor_check_2():
            buffer = False
        if not self.ins.check_auto_eviction():
            buffer = False
        
        if buffer:
            print("通过")
        else:
            self.print_.append(f"检查 LINSTOR 异常")
            print(f"不通过")

    # 检查 CoSAN Manager
    def check_cosan_manager(self):
        print("———— 检查 CoSAN Manager ————")
        buffer = True
        if not self.ins.check_pod_status():
            if self.ins.cosan_manager_controller:
                self.print_.append(f"检查 CoSAN Manager 时 pod 状态检查结果异常")
                buffer = False
        if not self.ins.check_gui():
            self.print_.append(f"检查 CoSAN Manager 时 GUI 检查结果异常")
            buffer = False
        
        if buffer:
            print("通过")
        else:
            print(f"不通过")

    def all_control(self):
        self.check_software()
        self.check_network()
        self.check_corosync()
        self.check_pacemaker_cluster()
        self.check_linstor_controller_ha()
        self.check_linstor()
        self.check_cosan_manager()

        if self.print_ == []:
            print("巡检项目都通过")
        else:
            print("\n总结：")
            for element in self.print_:
                print(element)
            print(f"具体请检查 logs/{self.logger.get_name()} 文件")
        
        self.logger.del_()