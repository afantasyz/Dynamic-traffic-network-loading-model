import pandas as pd
from Linkmodel import *
import math

class Trafficnet:
    def __init__(self,totalTime,version=1) -> None:
        #LTM可以选择最小链路通过时间来作为单位时间，减少计算，这里还是不压缩了，使用标准时间
        self.TotalTimePeriod=totalTime  #总时间
        self.sigma_periodLength=0   #单位时间
        self.T_periodSet=0  #单位时间集
        self.A_linkSet={}   #所有link
        self.N_nodeSet={}   #所有node
        self.AR_sourcelinkSet=[]    #出发link
        self.AS_sinklinkSet=[]  #终点link
        self.AG_generallinkSet=[]   #普通link
        self.RN_sourceNode=[]   #源节点
        self.GN_generalNode=[]  #普通节点
        self.SN_sinkNode=[]     #终点节点
        self.PathSet={}     #路径集合
        self.ODset=[]       #OD集合
        self.PathSetByOD={} #按OD对分类的路径
        self.DG_apt={}      #按路径分配后的Demad
        self.SG_apt={}      #Demand未积分版
        self.FG_apt={}      #从出口离开的车辆

        #输出变量
        self.SystemTravalTime=0  #
        self.SystemVariance=0   #
        self.travelTimeList={i:0 for i in range(1,self.TotalTimePeriod)}  #

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
                    
 
            #集合添加成员
            T=linkdf.loc[i,'type']
            if T=='R':
                self.AR_sourcelinkSet.append(i)
            elif T=='S':
                self.AS_sinklinkSet.append(i)
            elif T=='G':
                self.AG_generallinkSet.append(i)

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
        
        print("\n路径信息为\nThe path info is :")
        print(self.PathSet)
        print("\nOD对信息为\nThe OD info is :")
        print(self.ODset)
        print("\n路径和OD对关系\nThe path sort by OD is:")
        print(self.PathSetByOD)

        #输出计算结果
        print("\n系统通行总时间为:\n{}\n车辆通行时间方差为:{}".format\
              (self.SystemTravalTime,self.SystemVariance))
        print("\n从出口流出网络的信息为:\n需求量:\n{},\n完成量:\n{},\n时间分布:{}".format(self.SG_apt,self.FG_apt,self.travelTimeList))
        
    #生成路径
    def Trafficnet_generatePath(self):
        for i in self.AR_sourcelinkSet:
            for j in self.AS_sinklinkSet:
                self.ODset.append((i,j))
                self.PathSetByOD.update({(i,j):[]})
                path=[i]
                self.findPath(i,j,path[:])
        #按OD分类
        for i in self.PathSet.keys():
            self.PathSetByOD[(self.PathSet[i][0],self.PathSet[i][-1])].append(i)
            #给link的路径集添加相应路径
            for route in self.PathSet[i]:
                self.A_linkSet[route].PathSet.append(i)

    #递归寻路
    def findPath(self,pos,destination,path):
        nextnode=self.A_linkSet[pos].nextNode
        nextlink=self.N_nodeSet[nextnode].outLink
        for i in nextlink:
            path.append(i)
            if i==destination:               
                self.PathSet.update({len(self.PathSet):path[:]})
            else:
                self.findPath(i,destination,path[:])
            path.pop()

    #输出数据   导出文件
    def Trafficnet_getResult(self):
        #计算通行时间
        totalTranvelTime=0
        travelTimeByPath={i:0 for i in self.PathSet.keys()} #按路径分类的通行时间
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

                self.calculateTravelTime(Indict,Outdict)

        #求方差
        totalT=sum(self.travelTimeList[i]*i for i in self.travelTimeList.keys())
        totalV=sum(self.travelTimeList[i] for i in self.travelTimeList.keys())
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
    ### 程序运行到这里容易报错，由于计算机位数有限，分数中的无限小数转为double型时会损失精度,造成e-15正负的误差,故以下判断语句以0.001下看作0 ###
        while(len(inIndex)!=0 and len(outIndex)!=0):
            if Indict[i]<=0.0001 and len(inIndex)>0:
                i=inIndex.pop()
            if Outdict[j]<=0.0001 and len(outIndex)>0:
                j=outIndex.pop()            
            vechile=min(Indict[i],Outdict[j])
            self.travelTimeList[abs(j-i)]+=vechile
            Indict[i]=Indict[i]-vechile
            Outdict[j]=Outdict[j]-vechile

    #初始化变量部分
    def Trafficnet_init_U_V(self):
        for a in self.A_linkSet.keys():
            for t in range(self.TotalTimePeriod):
                for p in self.A_linkSet[a].PathSet:
                    self.A_linkSet[a].uv.URecord.update({(p,t):0})
                    self.A_linkSet[a].uv.VRecord.update({(p,t):0})
                self.A_linkSet[a].uv.UsumRecord.update({t:0})
                self.A_linkSet[a].uv.VsumRecord.update({t:0})

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
        #起始link更新
        for i in self.AR_sourcelinkSet:
            tepLink=self.A_linkSet[i]
            for p in tepLink.PathSet:
                tepu=self.DG_apt[i,p,t]
                tepLink.uv.URecord[p,t]=tepu
                tepLink.uv.UsumRecord[t]+=tepu

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
            
            #当前累计流赋值一下
            for i in inLink:
                self.A_linkSet[i].uv.VsumRecord[t]=self.A_linkSet[i].uv.VsumRecord[t-1]
            for j in outLink:
                self.A_linkSet[j].uv.UsumRecord[t]=self.A_linkSet[j].uv.UsumRecord[t-1]

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
                    path=self.PathSet[p]
                    aindex=path[path.index(i)+1]
                    if t-lastT>0 and tepS>0:
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
                if sumSij==0:
                    sumSij=1
                tepPer.append(Rj[j]/sumSij)
                
            #更新Rij部分和Gij
            for i in inLink:
                for j in outLink:
                    Rij[(i,j)]=min(tepPer)*Sij[(i,j)]
                    Gij[(i,j)]=min(Rij[(i,j)],Sij[(i,j)])
                    # print("The flow from {} to {} at time {} is {}".format(i,j,t,Gij[(i,j)]))
                    self.A_linkSet[i].uv.VsumRecord[t]+=Gij[(i,j)]
                    self.A_linkSet[j].uv.UsumRecord[t]+=Gij[(i,j)]

            #将Gij的数值更新u和v
            for i in inLink:
                tepLink=self.A_linkSet[i]
                for p in tepLink.PathSet:
                    path=self.PathSet[p]
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

if __name__=="__main__":
        
    example=Trafficnet(20)
    # example.Trafficnet_readcsv()

    # example.Trafficnet_printInfo()