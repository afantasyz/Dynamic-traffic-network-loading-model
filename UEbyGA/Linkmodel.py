
class U_V_Flow:
    def __init__(self) -> None:
        self.URecord={}     #累计流入流记录 {(p,t):num}
        self.VRecord={}     #累计流出流记录
        self.UsumRecord={}  #累计流入流记录 不记录路径{t:num}
        self.VsumRecord={}  #累计流出流记录 不记录路径
        #如果link是充电节点,会用到记录电车的流量{(p,t,T):num},其中t为当前时间，T为充电时间
        self.EVnum={}   #充电节点当容纳的车辆总数 {t:num}
        self.EVRecord={}    #当前充电节点的记录详情

    def U_V_updateInfo(self):
        pass

    def U_V_printInfo(self):
        print("U total info:",self.UsumRecord,"\nV total info:",self.VsumRecord)

class Nodemodel:
    def __init__(self,id) -> None:
        self.nid=id  #节点ID
        self.inLink=[]  #流入的link编号
        self.outLink=[] #流出的link编号
        self.nType=' '      #节点类型
    
    def Nodemodel_loadInfo(self):
        pass

    def Nodemodel_printInfo(self):
        print("node id:{}, type:{}, inLink:{}, ouLink:{}".format(self.nid,self.nType,self.inLink,self.outLink))

class Linkmodel:
    def __init__(self,id) -> None:
        #参数
        self.a_ID=id     #link编号
        self.lastNode=0   #入口节点编号
        self.nextNode=0   #出口节点编号
        self.linkType=' '   #link类别
        self.L_length=0   #link长度
        self.k_JamDensity=0  #堵塞密度
        self.q_MaxFlow=0  #最大容量
        self.v_FreeFlowSpeed=0    #自由车流速度
        self.w_BackwardSpeed=0    #反向传播车流速度
        self.If_inflowCapacity=[]   #入口流入限制
        self.Of_outflowCapacity=[]  #出口流出限制
        self.l_energyCost=0     #能级消耗
        #如果link类别是起始节点，则有需求量
        self.DG_Demand={}   #汽车通行需求 {t:{od:num}}
        self.DE_Demand={}   #电车通行需求  {t:{(od,el):num}}
        self.vt_FreeFlowTime=0    #自由通过的时间
        self.wt_BackwardTime=0    #反向通过的时间
        self.PathSet=[]    #经过此点的路径集 [id]
        #变量
        self.uv=U_V_Flow()   #累计流量记录

    #加载数据用
    def Linkmodel_loadInfo(self,linkColumn):
        #读取数据
        self.lastNode=linkColumn[0]
        self.nextNode=linkColumn[1]
        self.v_FreeFlowSpeed=linkColumn[2]
        self.w_BackwardSpeed=linkColumn[3]
        self.L_length=linkColumn[4]
        self.linkType=linkColumn[5]
        self.q_MaxFlow=linkColumn[6]
        #计算数据
        if(self.linkType=='G'):
            self.vt_FreeFlowTime=int(self.L_length/self.v_FreeFlowSpeed)
            self.wt_BackwardTime=int(self.L_length/self.w_BackwardSpeed)

    #打印自身信息 测试用
    def Linkmodel_printInfo(self):
        print("\nlink id:{}, lastnode:{}, nextnode:{}, v:{}, w:{}, L:{}, type:{}, q:{}".format(self.a_ID,\
            self.lastNode,self.nextNode,self.v_FreeFlowSpeed,self.w_BackwardSpeed,self.L_length,self.linkType,self.q_MaxFlow))
        # if(self.linkType=='R'):
        #     print("DemandOfSouce: time:( [start,end]:num )\n",self.DG_Demand)
        #     print("EV DemandOfSouce: time:( [start,end,el]:num )\n",self.DE_Demand)
        print("infolwCapacity: {}\noutfolwCapcity: {}".format(self.If_inflowCapacity,self.Of_outflowCapacity))
        print("所属的路径集为：\n",self.PathSet)
        self.uv.U_V_printInfo()
