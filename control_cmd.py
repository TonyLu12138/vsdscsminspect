#! /usr/bin/env python3
import os
import re
import sys
import textwrap
import time
import yaml

from base import Base
class Inspections:
    def __init__(self, logger):
        self.base = Base(logger)
        self.logger = logger
        self.localnode = {}
        self.clusternode = []
        self.cosan_manager_controller = None
        self.cosan_manager_console_IP = None
        self.bond = []

        self.update_yaml_from_config()

    def update_yaml_from_config(self):
        # 检查文件是否存在
        config_file = f"{os.path.dirname(os.path.realpath(sys.argv[0]))}/vsdscsminspect_config.yaml"
        if os.path.exists(config_file):
            with open(config_file, 'r') as file:
                try:
                    data = yaml.safe_load(file)

                    # 更新属性
                    self.localnode = data.get('LocalNode', {})
                    clusternode_data = data.get('ClusterNode', [])  # 获取 ClusterNode 数据

                    # 处理 ClusterNode 数据
                    if isinstance(clusternode_data, list):
                        self.clusternode = clusternode_data  # 设置 ClusterNode 到实例属性中
                    else:
                        print("ClusterNode 不是列表")
                        
                    self.cosan_manager_controller = data.get('CoSAN Manager controller', None)
                    self.cosan_manager_console_IP = data.get('CoSAN Manager console IP', None)
                    self.bond = data.get('Bond', [])

                except yaml.YAMLError as exc:
                    print(f"yaml 数据更新出现问题：{exc}")
        else:
            print(f"未找到 vsdscsminspect_config.yaml 配置文件。请检查 vsdscsminspect_config.yaml文件是否存在。")
            sys.exit()
        # print(f"self.localnode: {self.localnode}")
        # print(f"self.clusternode: {self.clusternode}")
        # print(f"self.cosan_manager_controller: {self.cosan_manager_controller}")
        # print(f"self.cosan_manager_console_IP: {self.cosan_manager_console_IP}")
        # print(f"self.bond: {self.bond}")

    # 检查软件
    def check_software_(self, service_name):
        try:
            command = f"systemctl is-enabled {service_name}"
            result = self.base.com(command).stdout
            self.logger.log(f"执行命令：{command} 结果：{result.strip()}")
            if result.strip() == "disabled":
                self.logger.log(f"{service_name} 已禁用\n")
                return True
            else:
                self.logger.log(f"ERROR - {service_name} 禁用失败\n")
                return False
        except Exception as e:
            print(f"检查{service_name}状态发生错误：{e}")
            self.logger.log(f"ERROR - 检查{service_name}状态发生错误：{e}")  # debug
            return False
        
    # 检查是否禁用无人值守升级成功
    def check_unattended_upgrades(self):
        try:
            command1 = f"systemctl is-enabled unattended-upgrades"
            command2 = f"systemctl is-active unattended-upgrades"
            result_enabled = self.base.com(command1)
            result_active = self.base.com(command2)
            if "disabled" in result_enabled.stdout or "non-zero" in result_enabled.stdout and "inactive" in result_active.stdout:
                return True
            else:
                return False
        except Exception as e:
            print(f"检查是否禁用无人值守升级发生错误：{e}")
            self.logger.log(f"ERROR - 检查是否禁用无人值守升级发生错误：{e}\n")  # debug
            return False

    # 检查配置文件参数是否修改成功
    def check_configuration_file(self):
        try:
            command1 = f"apt-config dump APT::Periodic::Update-Package-Lists"
            command2 = f"apt-config dump APT::Periodic::Unattended-Upgrade"
            result_Update_Package_Lists = self.base.com(command1)
            self.logger.log(f"执行结果：{result_Update_Package_Lists.stdout.strip()}")
            result_Unattended_Upgrade = self.base.com(command2)
            self.logger.log(f"执行结果：{result_Unattended_Upgrade.stdout.strip()}")
            if "0" not in result_Update_Package_Lists.stdout and "0" not in result_Unattended_Upgrade.stdout:
                return False
            else:
                return True
        except Exception as e:
            print(f"检查配置文件参数是否修改成功发生错误：{e}")
            self.logger.log(f"ERROR - 检查配置文件参数是否修改成功发生错误：{e}")  # debug
            return False
        
    # 检查 Bond 连接情况
    def check_bond_connections(self):
        all_bonds_passed = True

        for bond_config in self.bond:
            bond_name = bond_config.get('name')
            bond_speed = bond_config.get('speed')

            if not bond_name or not bond_speed:
                self.logger.log(f"ERROR - {bond_config} 未找到有效的 Bond 名称或速度")
                all_bonds_passed = False
                continue

            try:
                result = self.base.com(f'ethtool {bond_name}').stdout
                lines = result.split('\n')

                # 去除每行中的制表符
                for i in range(len(lines)):
                    lines[i] = lines[i].replace('\t', '')

                speed = "Default Speed"
                link_detected = False
                for line in lines:
                    if line.startswith('Speed:'):
                        speed = line
                    elif "Link detected: yes" in line:
                        link_detected = True

                # 正则表达式模式匹配速度
                speed_pattern = re.compile(r'\d+')

                # 寻找速度的数字部分
                speed_value = int(speed_pattern.search(speed).group()) if speed_pattern.search(speed) else 0

                # 获取速度数字，如果没有找到则将其设置为0
                bond_speed_value = int(re.search(r'\d+', bond_speed).group()) if re.search(r'\d+', bond_speed) else 0

                if bond_speed_value == speed_value and link_detected:
                    self.logger.log(f"{bond_name} 连接正常")
                else:
                    self.logger.log(f"ERROR - {bond_name} 连接异常")
                    all_bonds_passed = False


            except Exception as e:
                print(f"检查 Bond 连接情况出错: {e}")
                self.logger.log(f"ERROR - 检查 Bond 连接情况出错：{e}\n")
                return False

        return all_bonds_passed
    
    # 检查 Bond 
    def check_bond(self):
        all_bonds_passed = True

        bond_configurations = {
            'Transmit Hash Policy': 'layer3+4 (1)', 
            'MII Status': 'up', 
            'MII Polling Interval (ms)': '100', 
            'Up Delay (ms)': '0', 
            'Down Delay (ms)': '0', 
            'Peer Notification Delay (ms)': '0', 
            '802.3ad info': '', 
            'LACP rate': 'fast', 
            'Min links': '0', 
        }

        # 检查每个 Bond 配置
        for bond_config in self.bond:
            bond_name = bond_config.get('name')
            bond_mode = bond_config.get('mode')

            try:
                result = self.base.com(f"cat /proc/net/bonding/{bond_name}").stdout
                lines = result.split('\n')
                
                # 去除每行中的制表符
                for i in range(len(lines)):
                    lines[i] = lines[i].replace('\t', '')

                bonding_mode_line = next((line.strip() for line in lines if line.startswith('Bonding Mode:')), None)
                # 如果 bond_mode 不是 802.3ad 且存在于 bonding_mode_line 中且不为空，则直接返回 all_bonds_passed
                if bond_mode and bond_mode != '802.3ad' and bond_mode in bonding_mode_line and bonding_mode_line.strip():
                    return all_bonds_passed

                elif not bond_mode or bond_mode == '802.3ad':
                    # 将 result 按行分割为字典形式，与 bond_configurations 进行对比
                    result_dict = {}

                    for line in lines:
                        if ': ' in line:
                            key, value = line.split(': ', 1)
                            result_dict[key] = value
                        else:
                            result_dict[line] = ''

                    self.logger.log(f"将 result 按行分割为字典形式 result_dict: \n{result_dict}")

                    # print(f"bond_configurations: \n{bond_configurations}")
                    for key, value in bond_configurations.items():
                        # print(f"key: {key} value: {value}")
                        if key == '802.3ad info':
                            if key not in result_dict:
                                self.logger.log(f"ERROR - {bond_name} 连接异常")
                                all_bonds_passed = False
                        elif str(value) != str(result_dict.get(key, '')):
                            self.logger.log(f"ERROR - {bond_name} 连接异常: {key} 不匹配\nstr(value): {str(value)}\nresult_dict.get(key, ''): {result_dict.get(key, '')}")
                            all_bonds_passed = False
                else:
                    all_bonds_passed = False
            except Exception as e:
                self.logger.log(f"执行命令出错: {e}")
                all_bonds_passed = False

        return all_bonds_passed
    
    # 检查集群网络
    def check_cluster_network(self):
        cluster_network_passed = True

        localnode_cluster_ip = self.localnode.get('Cluster IP')
        localnode_iscsi_ip = self.localnode.get('iSCSI IP')
        clusternode_cips = []
        clusternode_iips = []


        if self.clusternode and isinstance(self.clusternode, list):
            for node in self.clusternode:
                if isinstance(node, dict):
                    clusternode_cips.append(node.get('Cluster IP', ''))
                    clusternode_iips.append(node.get('iSCSI IP', ''))
        
        if not localnode_cluster_ip or not localnode_iscsi_ip or not clusternode_iips  or not clusternode_cips:
            self.logger.log("未找到足够的 IP 地址信息")
            cluster_network_passed = False
        elif not self.ping_ip(localnode_cluster_ip, clusternode_cips):
            cluster_network_passed = False
        elif not self.ping_ip(localnode_iscsi_ip, clusternode_iips):
            cluster_network_passed = False
        
        return cluster_network_passed
    
    def ping_ip(self, loacl, cluster):
        ping = True

        for ip in cluster:
            command = f"ping -c 5 -I {loacl} {ip}"
            try:
                result = self.base.com(command).stdout

                # 打印 ping 输出
                # print(result)

                # 检查丢包率
                if 'packet loss' in result:
                    loss_rate = result.split('packet loss')[0].split(',')[-1].strip()
                    print(f"{loacl} ping {ip} 的丢包率：{loss_rate}")
                    self.logger.log(f"{loacl} ping {ip} 的丢包率：{loss_rate}")
                else:
                    self.logger.log(f"ERROR - result 中不包括'packet loss'")
                    ping = False
            except Exception as e:
                self.logger.log(f"ERROR - 执行 ping 命令出错：{e}")
                ping = False
        return ping
    
    # 检查 Corosync
    def corosync_check(self):
        try:
            command = "corosync-cfgtool -s"
            result = self.base.com(command).stdout.strip()
            lines = result.split('\n')

            # 去除每行中的制表符
            for i in range(len(lines)):
                lines[i] = lines[i].replace('\t', '')

            status_found = False
            for line in lines:
                if status_found:
                    if 'link enabled:1link connected:1' not in line:
                        self.logger.log(f"ERROR - 链接状态异常")
                        return False
                elif 'status:' in line:
                    status_found = True

            if status_found:
                self.logger.log("链接状态正常")
                return True
            else:
                self.logger.log(f"ERROR - 未找到链接状态")
                return False

        except Exception as e:
            self.logger.log(f"ERROR - 执行命令出错: {e}")
            return False
        
    # 检查 crm 相关配置
    def check_crm_status(self):
        node_list = list(map(lambda node: node['hostname'], self.clusternode))
        node_list.append(self.localnode.get("hostname"))
        online_nodes = self.get_online_nodes()  # 获取当前在线节点列表

        # print(f"set(node_list): {set(node_list)}")
        # print(f"set(online_nodes): {set(online_nodes)}")
        # print(f"{set(node_list) == set(online_nodes)}")

        if set(node_list) == set(online_nodes): # 比对在线节点和配置文件节点名称是否一致
            return True
        else:
            return False
        
    def get_online_nodes(self):
        try:
            # 执行 crm status 命令并捕获输出
            command = "crm status | cat"
            result = self.base.com(command).stdout
            
            # 提取在线节点信息
            lines = result.split('\n')

            # 去除每行中的制表符
            for i in range(len(lines)):
                lines[i] = lines[i].replace('\t', '')

            online_nodes = []
            found_node_list = False
            for line in lines:
                if found_node_list:
                    if 'Online:' in line and '[' in line:
                        online_nodes = line.split("[")[1].split("]")[0].split()
                        self.logger.log(f"online_nodes: {online_nodes}")
                        break
                elif line.startswith("Node List:"):
                    found_node_list = True

            if not found_node_list:
                self.logger.log(f"ERROR - 未找到 Node List 信息")

            return online_nodes
        except Exception as e:
            self.logger.log(f"ERROR - Error fetching cluster status: {e}")
        
    # 检查 resource-stickiness 值   
    def check_resource_stickiness(self):
        try:
            command = "crm conf show rsc-options"
            result = self.base.com(command).stdout

            if "resource-stickiness=1000" in result:
                self.logger.log("resource-stickiness 值正常")
                return True
            else:
                self.logger.log(f"ERROR - resource-stickiness 值异常")
                return False
            
        except Exception as e:
            self.logger.log(f"ERROR - 执行命令出错: {e}")
            return False
        
    # 检查值
    def check_value(self):
        try:
            command = "crm conf show cib-bootstrap-options"
            result = self.base.com(command).stdout

            # 检查集群节点数量
            # print(self.clusternode)
            node_list = list(map(lambda node: node['hostname'], self.clusternode))
            num_nodes = len(node_list) + 1  # 集群节点数量(包括一个本地节点)
            # print(num_nodes)
            # 检查 no-quorum-policy
            if num_nodes < 3:
                expected_no_quorum_policy = "ignore"
            else:
                expected_no_quorum_policy = "stop"

            # print("have-watchdog found:", "have-watchdog=false" in result)
            # print("cluster-infrastructure found:", "cluster-infrastructure=corosync" in result)
            # print("stonith-enabled found:", "stonith-enabled=false" in result)
            # print("no-quorum-policy found:", f"no-quorum-policy={expected_no_quorum_policy}" in result)

            # 检查 have-watchdog, cluster-infrastructure, stonith-enabled 和 no-quorum-policy 是否与预期值匹配
            if (
                "have-watchdog=false" in result and
                "cluster-infrastructure=corosync" in result and
                "stonith-enabled=false" in result and
                f"no-quorum-policy={expected_no_quorum_policy}" in result
            ):
                return True
            else:
                return False
            
        except Exception as e:
            self.logger.log(f"ERROR - 执行命令出错: {e}")
            return False
        
    # 检查资源存在
    def check_resource(self):
        try:
            check_resource_pass = True
            command = "crm status | cat"
            result = self.base.com(command).stdout

            if "vip_ctl" in result and "p_fs_linstordb" in result and "p_linstor-controller" in result:
                self.logger.log("资源存在")
            else:
                self.logger.log(f"ERROR - 资源不存在")
                check_resource_pass = False

            started_statuses = re.findall(r'Started\s(\S+)', result)
            # print(f"started_statuses: {started_statuses}")

            # 匹配 Masters 行
            masters_match = re.search(r'\* Masters:\s*\[\s*(.*?)\s*\]', result)
            if masters_match:
                masters = masters_match.group(1).split()
                # print(f"masters: {masters}")
            else:
                self.logger.log(f"ERROR - 未找到 Masters 行")
                check_resource_pass = False
            # 检查是否所有状态都一样
            if not all(status == started_statuses[0] for status in started_statuses):
                check_resource_pass = False
            elif not all(master in started_statuses for master in masters):
                check_resource_pass = False
                
            return check_resource_pass, masters
        except Exception as e:
            self.logger.log(f"ERROR - 执行命令出错: {e}")
            check_resource_pass = False
            return check_resource_pass, None
        
    # 检查数据库资源存在
    def check_database_resource(self):
        check_resource_pass, masters = self.check_resource()
        check_database_resource_pass = True

        command1 = "linstor r lv | grep linstordb"
        result1 = self.base.com(command1).stdout

        # 提取 LINSTOR 数据
        linstor_data = [line.strip().split('|') for line in result1.split('\n') if line.strip()]

        # 清洗数据，排除开头和结尾的空白字符
        linstor_data_cleaned = [[item.strip() for item in line if item.strip()] for line in linstor_data]

        # 显示 LINSTOR 数据
        # print("LINSTOR Database Status:")
        # print(linstor_data_cleaned)
        self.logger.log(f"提取 LINSTOR 数据: \n{linstor_data_cleaned}")
        # 检查 LINSTOR 数据是否符合条件
        for node in linstor_data_cleaned:
            if node[7] == 'InUse':
                if not masters[0] == node[0]:
                    check_database_resource_pass = False
            if 'UpToDate' not in node[8]:
                # print(f"node[8]: {node[8]}")
                check_database_resource_pass = False
        
        command2 = "drbdadm status linstordb"
        result2 = self.base.com(command2).stdout

        # 将结果拆分为单独的行
        lines = result2.splitlines()

        # 初始化标志变量
        disk_up_to_date = False
        peer_disk_up_to_date = True

        # 逐行检查状态
        for line in lines:
            if "disk:" in line:
                if "UpToDate" in line.split(":")[1]:
                    disk_up_to_date = True
            elif "peer-disk:" in line:
                if "UpToDate" not in line.split(":")[1]:
                    peer_disk_up_to_date = False

        print(f"disk_up_to_date: {disk_up_to_date}")
        print(f"peer_disk_up_to_date: {peer_disk_up_to_date}")
        print(f"check_database_resource_pass: {check_database_resource_pass}")
        # 检查状态是否符合要求
        if disk_up_to_date and peer_disk_up_to_date:
            pass
        else:
            check_database_resource_pass = False
        
        if check_database_resource_pass and check_resource_pass:
            return True
        else:
            return False
        
    # 检查 LINSTOR
    def linstor_check(self):
        # 获取节点名称和IP
        linstor_check_pass = True
        command = "linstor n l"
        result = self.base.com(command).stdout

        # 读取节点状态行并提取节点名称、状态和地址
        node_lines = result.splitlines()
        nodes = {}
        for line in node_lines[3:]:
            line = line.strip()
            if line and '|' in line:  # 检查该行是否包含分隔符 '┊'
                node_info = [item.strip() for item in line.split('|')]
                nodes[node_info[1]] = {
                    'NodeType': node_info[2],
                    'Addresses': node_info[3],
                    'State': node_info[4]
                }
        # print(nodes)
                
        # 检查节点名是否与配置文件中的节点名一致，并检查在线状态和 IP 地址
        for node in self.clusternode:
            hostname = node.get('hostname', '')
            cluster_ip = node.get('Cluster IP', '')
            if not self.matches_node_name(hostname, cluster_ip, nodes):
                linstor_check_pass = False
        
        # 本地节点
        hostname = self.localnode.get('hostname', '')
        cluster_ip = self.localnode.get('Cluster IP', '')
        if not self.matches_node_name(hostname, cluster_ip, nodes):
            linstor_check_pass = False
        return linstor_check_pass
    
    def matches_node_name(self, hostname, cluster_ip, nodes):
        # 检查节点名是否与配置文件中的节点名一致
        print(f"hostname: {hostname}")
        print(f"cluster_ip: {cluster_ip}")
        print(f"nodes: {nodes}")
        if hostname in nodes:
            # 检查状态是否为 Online
            if 'Online' in nodes[hostname]['State']:
                # 检查 IP 是否与配置文件中的集群 IP 一致
                if cluster_ip in nodes[hostname]['Addresses']:
                    self.logger.log(f"节点 {hostname} 在线，并且 IP 地址一致")
                    return True
                else:
                    self.logger.log(f"ERROR - 节点 {hostname} 在线，但 IP 地址与配置文件中的不一致")
                    return False
            else:
                self.logger.log(f"ERROR - 节点 {hostname} 不在线")
                return False
        else:
            self.logger.log(f"ERROR - 节点 {hostname} 不在状态信息中")
            return False
        
    # 检查 LINSTOR 检查是否所有节点至少有一个不为 DfltDisklessStorPool 的存储池且 State 为 Ok，FreeCapacity ┊ TotalCapacity 不为 0
    def linstor_check_2(self):
        # 获取节点名称和IP
        linstor_check_pass2 = False
        command = "linstor sp l"
        result = self.base.com(command).stdout

        # 读取节点状态行并提取节点名称、状态和地址
        node_lines = result.splitlines()
        nodes = []
        header = None

        for line in node_lines:
            line = line.strip()
            if line.startswith('|'):  # 处理表头
                if not header:
                    header = [item.strip() for item in line.split('|')]
                else:
                    node_info = [item.strip() for item in line.split('|')]
                    if len(node_info) != 3:
                        node_data = {header[i]: node_info[i] for i in range(len(header))}
                        nodes.append(node_data)

        print(nodes)
        # 检查 nodes
        for node in nodes:
            if node['StoragePool'] != 'DfltDisklessStorPool' and 'Ok' in node['State'] and node['FreeCapacity'] and node['TotalCapacity'] and node['FreeCapacity'] != '0 TiB' and node['TotalCapacity'] != '0 TiB':
                linstor_check_pass2 = True
                break 
        
        return linstor_check_pass2
    
    # 检查是否禁用 auto eviction
    def check_auto_eviction(self):
        command = "linstor controller lp | grep DrbdOptions/AutoEvictAllowEviction"
        result = self.base.com(command).stdout

        if "false" in result.lower():
            return True
        elif "true" in result.lower():
            return False
        else:
            self.logger.log(f"auto eviction 禁用检查失败")
            return False

    # 检查 POD 状态
    def check_pod_status(self):
        if self.cosan_manager_controller:
            check_pod_status_pass = True
            command = "kubectl get pod -A"
            result = self.base.com(command).stdout

            # 读取节点状态行并提取节点名称、状态和地址
            node_lines = result.splitlines()
            nodes = []
            header = None

            for line in node_lines:
                line = line.strip()
                if line and '  ' in line:  # 包含两个空格以上才处理
                    if not header:
                        header = [item.strip() for item in line.split()]
                    else:
                        node_info = [item.strip() for item in line.split()]
                        node_data = {header[i]: node_info[i] for i in range(len(header))}
                        nodes.append(node_data)

            pod_names = [
                'kube-flannel', 'coredns', 'etcd', 'kube-apiserver', 'kube-controller-manager',
                'kube-proxy', 'kube-scheduler', 'linstor-csi-controller-0', 'linstor-csi-node',
                'openebs-localpv-provisioner', 'snapshot-controller-0', 'default-http-backend',
                'kubectl', 'alertmanager-main-0', 'kube-state-metrics', 'node-exporter',
                'notification-manager-deployment', 'notification-manager-operator', 'prometheus-k8s-0',
                'prometheus-operator', 'thanos-ruler-kubesphere-0', 'ks-apiserver', 'ks-console',
                'ks-controller-manager', 'ks-installer'
            ]
            # 检查 nodes
            # 检查 pods
            for pod_name in pod_names:
                for node in nodes:
                    if pod_name in node.get('NAME'):
                        if node.get('STATUS') != 'Running':
                            check_pod_status_pass = False
                            self.logger.log(f"Pod NAME: {node.get('NAME')} 状态异常: {node.get('STATUS')}")

            return check_pod_status_pass
        else:
            return False

    # 检查 GUI
    def check_gui(self):
        command = f"curl {self.cosan_manager_console_IP}"
        result = self.base.com(command).stdout

        if f'''Redirecting to <a href="/login">/login</a>.''' in result:
            return True
        else:
            self.logger.log(f"ERROR - 检查 GUI失败")
            return False
