import pandas as pd
from Linkmodel import *
import math
import copy
import random

class Pathinfo:
    def __init__(self) -> None:
        self.path=[]    #路径信息
        self.isChargePath=0 #是否是充电路径
        self.chargeLink=[]  #路径中的充电link
        self.chargeTime={}  #充电link的充电时间 {a:t}
        self.totalEl=0      #路径消耗的总能级
        self.EltoChargeLink={}  #到各充电节点时已消耗能级
        self.isUsed=0   #该路径是否启用

    def Pathinfo_printInfo(self):
        print("路径：{}\n是否是充电路线:{}\n充电时间分布:{}\n累计消耗能级:{}\n充电站处消耗能级:{}\n是否采用:{}\n".format(self.path,self.isChargePath,self.chargeTime,self.totalEl,self.EltoChargeLink,self.isUsed))

#分配函数
def random_partition(m, n):
    if n <= 0:
        raise ValueError("Number of partitions (n) must be greater than zero.")   
    # 随机生成n-1个划分点
    partitions = sorted(random.sample(range(m), n-1))
    partitions = [0] + partitions + [m]   
    # 计算划分后的部分
    partitions_values = [partitions[i+1] - partitions[i] for i in range(n)]    
    return partitions_values

class Trafficnet:
    def __init__(self,totalTime,version=1) -> None:
        #LTM可以选择最小链路通过时间来作为单位时间，减少计算，这里还是不压缩了，使用标准时间
        #和系统有关的变量
        self.TotalTimePeriod=totalTime  #总时间
        self.sigma_periodLength=1   #单位时间
        self.T_periodSet=0  #单位时间集 =总时间/单位时间
        #节点和链路信息
        self.A_linkSet={}   #所有link
        self.N_nodeSet={}   #所有node
        self.AR_sourcelinkSet=[]    #出发link
        self.AS_sinklinkSet=[]  #终点link
        self.AG_generallinkSet=[]   #普通link
        self.AC_chargelinkSet=[]    #充电link
        self.RN_sourceNode=[]   #源节点
        self.GN_generalNode=[]  #普通节点
        self.SN_sinkNode=[]     #终点节点
        self.CN_chargeNode=[]   #充电节点
        #路径有关集合
        self.PathSet={}     #路径集合 {id:pathinfo} 第一存储的是正常搜索的路径，经处理后加入了电车额外信息
        self.ODset=[]       #OD集合
        self.PathSetByOD={} #按OD对分类的路径 {od:[pathid]} 第一次存储pathset未加工版，第二次存储加工后路径
        self.PathSetByOdforGv={}    #油车按OD对分类的路径 {od:[pathid]}
        self.PathSetByOdElforEv={}    #电车按OD对和能级分类的路径 {(od,el):[pathid]}
        self.DG_apt={}      #按路径分配后的Demad {(a,p,t):num}
        self.SG_apt={}      #Demand未积分版
        self.FG_apt={}      #从出口离开的车辆
        #电车有用的集合变量
        self.maxEnergy=0        #电车最大能量
        self.EL_energyLevel=10   #最大能级  
        self.consumeSpeed=1     #单位时间能级消耗 这里取1
        self.chargeSpeed=2   #充电速率
        self.index_demand_e=[]  #电车通行需求的索引 [(od,el)]
        self.elByOd={}      #电车需求中能级按od分类{Od:[el]}

        #输出变量
        self.SystemTravalTime=0  #系统通行时间
        self.SystemVariance=0   #通行时间方差
        self.travelTimeList={}  #{通行时间：车辆数}

        #使用的交通网络版本
        self.version=version
        self.lastDemandTime=0   #最晚出发的需求量   后续遗传算法时确定交叉范围用

    #初始化网络基本信息
    def Trafficnet_readcsv(self):
        #换一个文件路径
        filePath="data//network"+str(self.version)
        #link信息加载
        linkdf=pd.read_csv(filePath+"\link.csv")
        linkdf.set_index('id',inplace=True)
        #node信息加载
        nodedf=pd.read_csv(filePath+"//node.csv")
        nodedf.set_index('id',inplace=True)
        #最大流入量信息
        maxIndf=pd.read_csv(filePath+"\maxQin.csv")
        maxIndf.set_index('id',inplace=True)
        #最大流出量信息
        maxOutdf=pd.read_csv(filePath+"\maxQout.csv")
        maxOutdf.set_index('id',inplace=True)
        #通行需求加载
        demanddf=pd.read_csv(filePath+"\demand.csv")
        demanddf.set_index(['source_link','sink_link'],inplace=True)
        #电车通行需求加载
        demandEdf=pd.read_csv(filePath+'\demand_e.csv')
        demandEdf.set_index(['source_link','sink_link','el'],inplace=True)

        #初始化node
        for i in nodedf.index:
            #创建实例
            self.N_nodeSet.update({i:Nodemodel(i)})
            self.N_nodeSet[i].nType=nodedf.loc[i,'type']
            #添加集合
            T=nodedf.loc[i,'type']
            if T=='R':
                self.RN_sourceNode.append(i)
            elif T=='S':
                self.SN_sinkNode.append(i)
            elif T=='G':
                self.GN_generalNode.append(i)
            elif T=='C':
                self.CN_chargeNode.append(i)

        #初始化link
        for i in linkdf.index:
            #创建实例及基本信息
            self.A_linkSet.update({i:Linkmodel(i)})
            self.A_linkSet[i].Linkmodel_loadInfo(list(linkdf.loc[i]))
            #流入流出信息初始化
            self.A_linkSet[i].If_inflowCapacity=maxIndf.loc[i].tolist()
            self.A_linkSet[i].Of_outflowCapacity=maxOutdf.loc[i].tolist()
            #node添加信息
            self.N_nodeSet[linkdf.loc[i,'start']].outLink.append(i)
            self.N_nodeSet[linkdf.loc[i,'end']].inLink.append(i)
            #起始节点添加需求
            if linkdf.loc[i,'type']=='R':
                #非电车需求
                for c in demanddf.columns:
                    tepdic={}
                    for j in demanddf.index:
                        demand=demanddf.loc[j,c]
                        if j[0]==i:
                            tepdic.update({j:demand})
                        #更新下最晚需求时间
                        if demand>0 and int(c)>self.lastDemandTime:
                            self.lastDemandTime=int(c)
                    self.A_linkSet[i].DG_Demand.update({int(c):tepdic})
                #电车需求
                self.index_demand_e=demandEdf.index.tolist()
                for c in demandEdf.columns:
                    tepdic={}
                    for k in demandEdf.index:
                        demand=demandEdf.loc[k,c]
                        if k[0]==i:
                            tepdic.update({k:demand})
                        #更新下最晚需求时间
                        if demand>0 and int(c)>self.lastDemandTime:
                            self.lastDemandTime=int(c)
                    self.A_linkSet[i].DE_Demand.update({int(c):tepdic})
                                             
            #集合添加成员
            T=linkdf.loc[i,'type']
            if T=='R':
                self.AR_sourcelinkSet.append(i)
            elif T=='S':
                self.AS_sinklinkSet.append(i)
            elif T=='G':
                self.AG_generallinkSet.append(i)
            elif T=='C':
                self.AC_chargelinkSet.append(i)

        #初始化路径
        self.Trafficnet_generatePath()
        # for i in self.A_linkSet:
        #     i.uv.U_V_loadInfo(self.ODset,self.PathSet)

    #打印测试数据
    def Trafficnet_printInfo(self):
        print("\n网络节点信息为\nThe info of TraficcNet Node is:")  
        for i in self.N_nodeSet.keys():
            self.N_nodeSet[i].Nodemodel_printInfo()

        print("\n网络链路信息为\nThe info of TraficcNet Link is:") 
        for i in self.A_linkSet.keys():
            self.A_linkSet[i].Linkmodel_printInfo()

        print("\n集合分类信息为\nThe info of TraficcNet Set is:") 
        print("AR:{}\nAS:{}\nAG:{}\nRN:{}\nSN{}\nGN:{}".format(self.AR_sourcelinkSet,self.AS_sinklinkSet,self.AG_generallinkSet,\
                    self.RN_sourceNode,self.SN_sinkNode,self.GN_generalNode))
        
        # print("\n路径信息为\nThe path info is :")
        # for i in self.PathSet:
        #     self.PathSet[i].Pathinfo_printInfo()
        print("\nOD对信息为\nThe OD info is :")
        print(self.ODset)
        print("\n路径按OD对对应信息为\nThe OD info is :")
        print(self.PathSetByOD)
        print("\nOD和对应能级需求\nThe path sort by OD is:")
        print(self.elByOd)
        print("\n油车路径和OD对关系\nThe path sort by OD is:")
        print(self.PathSetByOdforGv)
        print("\n电车路径和ODel对关系\nThe path sort by OD is:")
        print(self.PathSetByOdElforEv)

        #输出计算结果
        print("\n系统通行总时间为:\n{}\n车辆通行时间方差为:{}".format\
              (self.SystemTravalTime,self.SystemVariance))
        # print("\n从出口流出网络的信息为:\n需求量:\n{},\n完成量:\n{},\n时间分布:{}".format(self.SG_apt,self.FG_apt,self.travelTimeList))
        print("\n从出口流出网络的信息为:\n时间分布:{}".format(self.travelTimeList))
        
    #生成路径
    def Trafficnet_generatePath(self):
        for i in self.AR_sourcelinkSet:
            for j in self.AS_sinklinkSet:
                self.ODset.append((i,j))
                self.PathSetByOD.update({(i,j):[]})
                self.PathSetByOdforGv.update({(i,j):[]})
                self.elByOd.update({(i,j):[]})
                path=[i]
                self.findPath(i,j,path)

        for i in self.index_demand_e:
            self.PathSetByOdElforEv.update({i:[]})
            self.elByOd[(i[0],i[1])].append(i[2])

        #处理路径，区分油车和电车
        self.Trafficnet_ProcessPath()

        #给pathsetbyod重新添加内容
        for od in self.ODset:
            self.PathSetByOD[od].clear()

        #给link添加所用路径
        for p in self.PathSet:
            if self.PathSet[p].isUsed==1:
                self.PathSetByOD[(self.PathSet[p].path[0],self.PathSet[p].path[-1])].append(p)
                for route in self.PathSet[p].path:
                    self.A_linkSet[route].PathSet.append(p)

    #递归寻路
    def findPath(self,pos,destination,path):
        nextnode=self.A_linkSet[pos].nextNode
        nextlink=self.N_nodeSet[nextnode].outLink
        for i in nextlink:
            if i != pos:
                path.append(i)
                if i==destination:
                    pathcell=Pathinfo()
                    pathcell.path=path[:]
                    self.PathSetByOD[(path[0],path[-1])].append(len(self.PathSet))               
                    self.PathSet.update({len(self.PathSet):pathcell})
                else:
                    self.findPath(i,destination,path[:])
                path.pop()

    #处理路径信息
    def Trafficnet_ProcessPath(self):
        #先给路径pathinfo进行处理
        for p in self.PathSet:
            tepPathinfo=self.PathSet[p]
            cost=0
            for route in tepPathinfo.path:
                cost+=self.A_linkSet[route].vt_FreeFlowTime  #因为能级和时间消耗正相关
                if self.A_linkSet[route].linkType=='C':
                    tepPathinfo.isChargePath=1
                    tepPathinfo.chargeLink.append(route)
                    tepPathinfo.chargeTime.update({route:0})
                    tepPathinfo.EltoChargeLink.update({route:cost})
            tepPathinfo.totalEl=cost

        #给油车用路径分类
        for p in self.PathSet:
            if self.PathSet[p].isChargePath==0:
                self.PathSetByOdforGv[self.PathSet[p].path[0],self.PathSet[p].path[-1]].append(p)
                self.PathSet[p].isUsed=1

        #处理完后进行电车路径分类
        #####################此处路径规划体现了电车充电策略的选择，具有很多中方案选择，为了简单这里的方案为：最小额度的充电，以维持走到终点或下一个充电节点###################
        #####################充电方案算法的研究，不在本代码的范围内##########################
        for od in self.ODset:
            for e in self.elByOd[od]:
                for p in self.PathSetByOD[od]:                
                    el=e  #当前累计能级
                    chargeTime=0    #记录充电次数
                    tepPathinfo=copy.deepcopy(self.PathSet[p])
                    #如果该路径是非充电路径
                    if tepPathinfo.isChargePath==0:
                        if e > tepPathinfo.totalEl:
                            self.PathSetByOdElforEv[od[0],od[1],e].append(p)
                        continue
                    #如果该路径是充电路径
                    for ac in tepPathinfo.chargeLink:
                        #如果当前累计能级不足以走到下一个充电站,路径不可行
                        if el<tepPathinfo.EltoChargeLink[ac]:
                            break
                        #如果当前累计能级小于总的通行能级需求，则充电
                        if el<tepPathinfo.totalEl:
                            #计算需要充电量，这里为{到达终点所需能级-自身累计能量，自身能级容量-当前剩余能量}中的小值
                            chargeTime+=1
                            chargeEl=min(self.EL_energyLevel-el+tepPathinfo.EltoChargeLink[ac],tepPathinfo.totalEl-el)
                            tepPathinfo.chargeTime[ac]=math.ceil(chargeEl/self.chargeSpeed)
                            el+=chargeEl
                        #如果该路径已经可行
                        if el>=tepPathinfo.totalEl and chargeTime>0:
                            id=len(self.PathSet)
                            tepPathinfo.isUsed=1
                            self.PathSet.update({id:tepPathinfo})
                            self.PathSetByOdElforEv[od[0],od[1],e].append(id)
                            break
                    #剔除充电路径中充电时间为0的link节点，此部分多余
                    if el>=tepPathinfo.totalEl:
                        for a in tepPathinfo.chargeLink:
                            if tepPathinfo.chargeTime[a]==0:
                                tepPathinfo.path.remove(a)

            #如果此电车需求搜索到的可行路径为0，说明这个需求到达不了终点，应抛出异常
            if len(self.PathSetByOdElforEv[od[0],od[1],e])==0:
                print("电车需求{}未找到可行路径".format(od[0],od[1],e))                   
                

    #输出数据   导出文件
    def Trafficnet_getResult(self):
        #计算通行时间
        totalTranvelTime=0
        travelTimeByPath={i:0 for i in self.PathSet.keys() if self.PathSet[i].isUsed==1} #按路径分类的通行时间
        for t in range(1,self.TotalTimePeriod):
            for i in self.AR_sourcelinkSet:
                tepLink=self.A_linkSet[i]
                totalTranvelTime+=tepLink.uv.UsumRecord[t]
                for p in tepLink.PathSet:
                    travelTimeByPath[p]+=tepLink.uv.URecord[p,t]

            for j  in self.AS_sinklinkSet:
                tepLink=self.A_linkSet[j]
                totalTranvelTime-=tepLink.uv.UsumRecord[t]
                for p in tepLink.PathSet:
                    travelTimeByPath[p]-=tepLink.uv.URecord[p,t]

        self.SystemTravalTime=totalTranvelTime

        #计算每个时刻到达出口sinklink的车流
        for i in self.AS_sinklinkSet:
            tepLink=self.A_linkSet[i]
            for t in range(1,self.TotalTimePeriod):
                for p in tepLink.PathSet:
                    vechileNum=tepLink.uv.URecord[p,t]-tepLink.uv.URecord[p,t-1]
                    self.FG_apt.update({(i,p,t):vechileNum})

        #计算每份车流的通行时间
        for od in self.ODset:
            for p in self.PathSetByOD[od]:
                Indict={}
                Outdict={}

                for t in range(1,self.TotalTimePeriod):
                    tepNum=self.SG_apt[od[0],p,t]
                    if tepNum>0.0001:
                        Indict.update({t:tepNum})
                    tepNum=self.FG_apt[od[1],p,t] 
                    if tepNum>0.0001:  
                        Outdict.update({t:tepNum})

                #计算未到达终点的车流
                sumin=sum(i for i in Indict.values())
                sumout=sum(i for i in Outdict.values())
                if sumout<sumin:
                    Outdict.update({self.TotalTimePeriod:sumin-sumout})
                #计算通行时间
                if len(Outdict)>0:
                    self.calculateTravelTime(Indict,Outdict)

        #求方差
        totalT=sum(self.travelTimeList[i]*i for i in self.travelTimeList.keys())
        totalV=sum(self.travelTimeList[i] for i in self.travelTimeList.keys())
        if totalV>0:
            mean=totalT/totalV
            self.SystemVariance=sum(((i-mean)**2)*self.travelTimeList[i] for i in self.travelTimeList.keys())/totalV

        # #输出计算结果
        # print("\n系统通行总时间为:\n{},\n按路径区别的通行总时间为:\n{},\n车辆通行时间方差为:{}\n系统通行时间平均值为:{}".format\
        #       (totalTranvelTime,travelTimeByPath,self.SystemVariance,mean))
        # print("\n从出口流出网络的信息为:\n需求量:\n{},\n完成量:\n{},\n时间分布:{}\n".format(self.SG_apt,self.FG_apt,self.travelTimeList))

    #按对齐的原则计算车辆通行时间
    def calculateTravelTime(self,Indict,Outdict):
        inIndex=list(Indict.keys())
        outIndex=list(Outdict.keys())
        i=inIndex.pop()
        j=outIndex.pop()
        #双指针递减
    ### 由于浮点数位数有限，分数中的无限小数转为double型时会损失精度,造成e-15正负的误差,故以下判断语句以0.001下看作0 ###
    ### 程序运行到这里容易报错，主要是由于输入数据过大或系统运行时间过小，导致给定时间内不能完成通行需求###
        while(len(inIndex)!=0 and len(outIndex)!=0):
            if Indict[i]<=0.001 and len(inIndex)>0:
                i=inIndex.pop()
            if Outdict[j]<=0.001 and len(outIndex)>0:
                j=outIndex.pop()            
            vechile=min(Indict[i],Outdict[j])
            self.travelTimeList[abs(j-i)]+=vechile
            Indict[i]=Indict[i]-vechile
            Outdict[j]=Outdict[j]-vechile

    #初始化变量部分
    def Trafficnet_init_U_V(self):
        #变量初始化
        for a in self.A_linkSet.keys():
            for t in range(self.TotalTimePeriod):
                for p in self.A_linkSet[a].PathSet:
                    self.A_linkSet[a].uv.URecord.update({(p,t):0})
                    self.A_linkSet[a].uv.VRecord.update({(p,t):0})
                    for T in range(self.EL_energyLevel):
                        self.A_linkSet[a].uv.EVRecord.update({(p,t,T):0})
                self.A_linkSet[a].uv.UsumRecord.update({t:0})
                self.A_linkSet[a].uv.VsumRecord.update({t:0})
                self.A_linkSet[a].uv.EVnum.update({t:0})
        #统计数据初始化
        self.travelTimeList.clear()
        self.travelTimeList={i:0 for i in range(1,self.TotalTimePeriod)}  #{通行时间：车辆数}

    #按照输入的分配方案初始化DG
    def Trafficnet_loadSolution(self,DG_apt):
        self.DG_apt=DG_apt.copy()
       #进行累加操作
        self.SG_apt=DG_apt
        for ar in self.AR_sourcelinkSet:
            for p in self.A_linkSet[ar].PathSet:
                for t in range(2,self.TotalTimePeriod):    #这里有个常数2
                    self.DG_apt[ar,p,t]+=self.DG_apt[ar,p,t-1]   

    #网络更新
    def Trafficnet_update(self,t):
        #更新之前累计流赋值
        for i in self.A_linkSet:
            if self.A_linkSet[i].linkType!='R':
                self.A_linkSet[i].uv.VsumRecord[t]=self.A_linkSet[i].uv.VsumRecord[t-1]
                self.A_linkSet[i].uv.UsumRecord[t]=self.A_linkSet[i].uv.UsumRecord[t-1]

        #起始link更新
        for i in self.AR_sourcelinkSet:
            tepLink=self.A_linkSet[i]
            for p in tepLink.PathSet:
                tepu=self.DG_apt[i,p,t]
                tepLink.uv.URecord[p,t]=tepu
                tepLink.uv.UsumRecord[t]+=tepu

        #充电link更新
        #################；由于充电link为道路外部的部分，故其计算时没有考虑FIFO约束###############
        for n in self.CN_chargeNode:
            #用到的数据
            inLink=self.N_nodeSet[n].inLink
            outLink=self.N_nodeSet[n].outLink
            Si={}   #发出流Si
            Rj={}   #接收流Rj
            Sij={}  #从编号i到j的发出流
            Rij={}  #从编号i到j的接收流
            Gij={}  #从编号i到j的实际流量
            #每个link中各种车流按路径分布的比例
            flowbyPath={}
            flowbyNext={}

            chargeLink=0
            #找到充电link,流入节点和流出节点
            #初始化变量
            for i in inLink:
                flowbyPath.update({i:{}})
                for j in outLink:
                    Sij.update({(i,j):0})
                    Gij.update({(i,j):0})
                    Rij.update({(i,j):0})
                    flowbyNext.update({(i,j):0})
                    if i==j:
                        chargeLink=i

            # #当前累计流赋值一下
            # for i in inLink:
            #     self.A_linkSet[i].uv.VsumRecord[t]=self.A_linkSet[i].uv.VsumRecord[t-1]
            # for j in outLink:
            #     self.A_linkSet[j].uv.UsumRecord[t]=self.A_linkSet[j].uv.UsumRecord[t-1]

            self.A_linkSet[chargeLink].uv.EVnum[t]=self.A_linkSet[chargeLink].uv.EVnum[t-1]
            #对充电的车辆进行更新，剩余充电时间减一
            tepLink=self.A_linkSet[chargeLink]
            for p in tepLink.PathSet:
                tepLink.uv.EVRecord[(p,t,0)]=tepLink.uv.EVRecord[(p,t-1,1)]+tepLink.uv.EVRecord[(p,t-1,0)]
                for T in range(2,math.ceil(self.EL_energyLevel/self.chargeSpeed)):  #这里也是常数2
                    tepLink.uv.EVRecord[(p,t,T-1)]=tepLink.uv.EVRecord[(p,t-1,T)]

            #计算Sij
            for i in inLink:
                tepLink=self.A_linkSet[i]
                #如果i为一般link
                if tepLink.linkType!='C':
                    lastT=tepLink.vt_FreeFlowTime
                    tepS=0
                    if t-lastT>0:
                        tepS=tepLink.uv.UsumRecord[t-lastT]-tepLink.uv.VsumRecord[t-1]
                        Si.update({i:min(tepLink.Of_outflowCapacity[0],tepS)})
                    else:
                        Si.update({i:0})
                    #更新Sij部分
                    for p in tepLink.PathSet:
                        path=self.PathSet[p].path
                        aindex=path[path.index(i)+1]
                        if t-lastT>0 and tepS>0.001:
                            per=(tepLink.uv.URecord[p,t-lastT]-tepLink.uv.VRecord[p,t-1]) /tepS
                            flowbyPath[i].update({p:per})
                            flowbyNext[i,aindex]+=per
                            Sij[i,aindex]+=Si[i]*per
                        else:
                            flowbyPath[i].update({p:0})
                #如果i是充电节点
                ###按照常理来说，由于充电节点的可容纳车辆数远小于link的流入流出容量，与车辆充电时间比进入节点的时间可忽略，
                #故此处Si直接认为是充电完毕的车辆数，不做min操作
                else:
                    se=0
                    #先计算Si
                    for p in tepLink.PathSet:
                        num=tepLink.uv.EVRecord[(p,t,0)]
                        se+=num
                    Si.update({i:se})    
                    #在求比例
                    for p in tepLink.PathSet:
                        num=tepLink.uv.EVRecord[(p,t,0)]
                        if num>0.001:
                            #查找下一个link标号
                            path=self.PathSet[p].path
                            aindex=path[path.index(i)+1]
                            Sij[i,aindex]+=num
                            per=num/se
                            flowbyPath[i].update({p:per})
                            flowbyNext[(i,aindex)]+=per
                        else:
                            flowbyPath[i].update({p:0})

            #计算Rj
            for j in outLink:
                tepLink=self.A_linkSet[j]
                #如果i为一般link
                if tepLink.linkType!='C':
                    lastT=tepLink.wt_BackwardTime
                    if t-lastT>0:
                        Rj.update({j:min(tepLink.If_inflowCapacity[0],tepLink.uv.VsumRecord[t-lastT]+tepLink.q_MaxFlow-tepLink.uv.UsumRecord[t-1])})
                    else:
                        Rj.update({j:min(tepLink.If_inflowCapacity[0],tepLink.q_MaxFlow)})

                #如果i是充电节点
                else:
                    restCap=tepLink.q_MaxFlow-tepLink.uv.EVnum[t]
                    Rj.update({j:min(restCap,tepLink.If_inflowCapacity[0])})

            #更新Gij
            for i in inLink:
                for j in outLink:
                    if Sij[(i,j)]>0.001:
                        Rij[(i,j)]=Sij[(i,j)]*Rj[j]/sum(Sij[(k,j)] for k in inLink)
                    else:
                        Rij[(i,j)]=Rj[j]
                    Gij[(i,j)]=min(Rij[(i,j)],Sij[(i,j)])
                    self.A_linkSet[i].uv.VsumRecord[t]+=Gij[(i,j)]
                    self.A_linkSet[j].uv.UsumRecord[t]+=Gij[(i,j)]
                    if i==chargeLink:
                        self.A_linkSet[i].uv.EVnum[t]-=Gij[(i,j)]
                    if j==chargeLink:
                        self.A_linkSet[j].uv.EVnum[t]+=Gij[(i,j)]

            #用Gij更新uv,由路径p区分
            for i in inLink:
                tepLink=self.A_linkSet[i]
                for p in tepLink.PathSet:
                    path=self.PathSet[p].path
                    #查找下一个link标号
                    aindex=path[path.index(i)+1]
                    tepNum=tepLink.uv.VRecord[p,t-1]
                    incNum=0
                    if flowbyNext[(i,aindex)]>0:
                        incNum=Gij[(i,aindex)]*(flowbyPath[i][p]/flowbyNext[(i,aindex)])
                        tepNum+=incNum
                    tepLink.uv.VRecord[p,t]=tepNum
                    self.A_linkSet[aindex].uv.URecord[p,t]=tepNum
                    #充电节点的Evrecord更新
                    if aindex==chargeLink:
                        chargeTime=self.PathSet[p].chargeTime[aindex]
                        self.A_linkSet[aindex].uv.EVRecord[(p,t,chargeTime)]+=incNum
                    if i==chargeLink:
                        tepLink.uv.EVRecord[(p,t,0)]-=incNum

        #一般link更新
        for n in self.GN_generalNode:           
            #用到的基本数据
            inLink=self.N_nodeSet[n].inLink
            outLink=self.N_nodeSet[n].outLink
            Si={}   #发出流Si
            Rj={}   #接收流Rj
            Sij={}  #从编号i到j的发出流
            Rij={}  #从编号i到j的接收流
            Gij={}  #从编号i到j的实际流量
            #每个link中各种车流按路径分布的比例
            flowbyPath={}
            flowbyNext={}
            for i in inLink:
                flowbyPath.update({i:{}})
                for j in outLink:
                    Sij.update({(i,j):0})
                    Rij.update({(i,j):0})
                    Gij.update({(i,j):0})
                    flowbyNext.update({(i,j):0})
            
            # #当前累计流赋值一下
            # for i in inLink:
            #     self.A_linkSet[i].uv.VsumRecord[t]=self.A_linkSet[i].uv.VsumRecord[t-1]
            # for j in outLink:
            #     self.A_linkSet[j].uv.UsumRecord[t]=self.A_linkSet[j].uv.UsumRecord[t-1]

           #更新Si的部分
            for i in inLink:
                tepLink=self.A_linkSet[i]
                lastT=tepLink.vt_FreeFlowTime
                tepS=0
                if t-lastT>0:
                    tepS=tepLink.uv.UsumRecord[t-lastT]-tepLink.uv.VsumRecord[t-1]
                    Si.update({i:min(tepLink.Of_outflowCapacity[0],tepS)})
                else:
                    Si.update({i:0})
                #更新Sij部分
                for p in tepLink.PathSet:
                    path=self.PathSet[p].path
                    aindex=path[path.index(i)+1]
                    if t-lastT>0 and tepS>0.001:
                        per=(tepLink.uv.URecord[p,t-lastT]-tepLink.uv.VRecord[p,t-1]) /tepS
                        flowbyPath[i].update({p:per})
                        flowbyNext[i,aindex]+=per
                        Sij[i,aindex]+=Si[i]*per 
                    else:
                        flowbyPath[i].update({p:0})

            #更新Rj部分
            tepPer=[]
            for j in outLink:
                tepLink=self.A_linkSet[j]
                lastT=tepLink.wt_BackwardTime
                if t-lastT>0:
                    Rj.update({j:min(tepLink.If_inflowCapacity[0],tepLink.uv.VsumRecord[t-lastT]+tepLink.q_MaxFlow-tepLink.uv.UsumRecord[t-1])})
                else:
                    Rj.update({j:min(tepLink.If_inflowCapacity[0],tepLink.q_MaxFlow)})
                #此处计算FIFO约束
                sumSij=0
                for i in inLink:
                    sumSij+=Sij[(i,j)]
                if sumSij<=0:
                    sumSij=1
                tepPer.append(Rj[j]/sumSij)

            minper=min(tepPer)   
            #更新Rij部分和Gij
            for i in inLink:
                for j in outLink:
                    Rij[(i,j)]=minper*Sij[(i,j)]
                    Gij[(i,j)]=min(Rij[(i,j)],Sij[(i,j)])
                    # print("The flow from {} to {} at time {} is {}".format(i,j,t,Gij[(i,j)]))
                    self.A_linkSet[i].uv.VsumRecord[t]+=Gij[(i,j)]
                    self.A_linkSet[j].uv.UsumRecord[t]+=Gij[(i,j)]

            #将Gij的数值更新u和v
            for i in inLink:
                tepLink=self.A_linkSet[i]
                for p in tepLink.PathSet:
                    path=self.PathSet[p].path
                    aindex=path[path.index(i)+1]
                    tepNum=tepLink.uv.VRecord[p,t-1]
                    if flowbyNext[(i,aindex)]>0:
                        tepNum+=Gij[(i,aindex)]*(flowbyPath[i][p]/flowbyNext[(i,aindex)])
                    tepLink.uv.VRecord[p,t]=tepNum
                    self.A_linkSet[aindex].uv.URecord[p,t]=tepNum

    #完成动态网络加载
    def Trafficnet_Run(self):
        for i in range(1,self.TotalTimePeriod):
            self.Trafficnet_update(i)

    #将运行结果导出文件
    def Trafficnet_SolutionFile(self):
        pass

    #生成初始的一个解决方案
    #从main文件中偷来的，用来调试
    def Trafficnet_getInitalSolution(self):
        #初始化需求方案
        DG_apt={}
        for ar in self.AR_sourcelinkSet:
            for t in range(1,self.TotalTimePeriod):
                for p in self.A_linkSet[ar].PathSet:
                    if self.PathSet[p].isUsed==1:
                        DG_apt.update({(ar,p,t):0})
        #随机路径选择
        for ar in self.AR_sourcelinkSet:
            tepLink=self.A_linkSet[ar]
            for t in range(1,self.TotalTimePeriod):
                #油车路径分配
                for od in tepLink.DG_Demand[t].keys():
                    pathNum=len(self.PathSetByOdforGv[od])
                    dnum=tepLink.DG_Demand[t][od]
                    solution=[0]*pathNum
                    if(dnum>0):
                        solution=random_partition(dnum,pathNum)
                        # print(solution)
                    #根据分配数给DG赋值
                    for i in range(pathNum):
                        DG_apt[ar,self.PathSetByOdforGv[od][i],t]+=solution[i]
                #电车路径分配
                for odel in tepLink.DE_Demand[t]:
                    pathNum=len(self.PathSetByOdElforEv[odel])
                    dnum=tepLink.DE_Demand[t][odel]
                    solution=[0]*pathNum
                    if(dnum>0):
                        solution=random_partition(dnum,pathNum)
                    #根据分配数给DG赋值
                    for i in range(pathNum):
                        DG_apt[ar,self.PathSetByOdElforEv[odel][i],t]+=solution[i]
        self.Trafficnet_loadSolution(DG_apt)

if __name__=="__main__":
        
    example=Trafficnet(20,3)
    example.Trafficnet_readcsv()
    example.Trafficnet_getInitalSolution()
    example.Trafficnet_init_U_V()
    example.Trafficnet_Run()
    example.Trafficnet_getResult()
    example.Trafficnet_printInfo()
